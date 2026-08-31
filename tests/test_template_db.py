import shlex
from pathlib import Path

import pytest

from lib.scripts import template_db


@pytest.mark.parametrize("name", ["agent", "agent_1", "a" * 31])
def test_valid_instance_names_pass(name):
    assert template_db.validate_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        None,
        "",
        "Agent",
        "1agent",
        "agent-1",
        "agent; DROP DATABASE postgres",
        "a" * 32,
        "otr_template",
        "postgres",
        "template1",
    ],
)
def test_invalid_instance_names_are_rejected(name):
    with pytest.raises(ValueError):
        template_db.validate_name(name)


@pytest.mark.parametrize("port", [5432, 5433])
def test_guard_rejects_reserved_ports(monkeypatch, port):
    monkeypatch.setattr(template_db.config, "template_db_port", port)

    with pytest.raises(RuntimeError):
        template_db.guard()


def test_guard_rejects_the_application_container(monkeypatch):
    monkeypatch.setattr(template_db.config, "template_db_container", "otr-test-db")

    with pytest.raises(RuntimeError):
        template_db.guard()


def test_guard_accepts_the_dedicated_container():
    template_db.guard()


def test_seed_steps_recreate_and_flag_the_template():
    flag_off, terminate, drop, create, restore, flag_on = template_db.seed_steps(
        Path("/dumps/a b.gz")
    )

    assert "datistemplate = false" in flag_off[-1]
    assert "datistemplate = true" in flag_on[-1]
    assert f"datname = '{template_db.TEMPLATE}'" in terminate[-1]
    assert drop[-1] == "DROP DATABASE IF EXISTS otr_template"
    assert create[-1] == "CREATE DATABASE otr_template"
    assert restore[:4] == ["bash", "-o", "pipefail", "-c"]
    assert restore[-1].startswith("gunzip -c '/dumps/a b.gz' | docker exec -i")
    assert "-d otr_template -v ON_ERROR_STOP=1 --quiet" in restore[-1]

    for step in (flag_off, terminate, drop, create, flag_on):
        assert step[step.index("-d") + 1] == "postgres"
        assert step[:4] == ["docker", "exec", "-i", "otr-template-test-db"]


def test_create_copies_the_template():
    terminate, create = template_db.create_steps("agent_1")

    assert f"datname = '{template_db.TEMPLATE}'" in terminate[-1]
    assert create[-1] == "CREATE DATABASE agent_1 TEMPLATE otr_template"


def test_drop_terminates_then_drops():
    terminate, drop = template_db.drop_steps("agent_1")

    assert "datname = 'agent_1'" in terminate[-1]
    assert drop[-1] == "DROP DATABASE IF EXISTS agent_1"


def test_list_excludes_templates_and_system_databases():
    sql = template_db.list_command()[-1]

    assert "pg_size_pretty" in sql
    assert "datistemplate = false" in sql
    assert "NOT IN ('postgres', 'otr_template')" in sql


def test_container_runs_on_the_configured_port():
    cmd = shlex.join(template_db.create_container_command())

    assert "--name otr-template-test-db" in cmd
    assert "-p 127.0.0.1:5434:5432" in cmd
    assert "-v otr-template-test-db-data:/var/lib/postgresql/data" in cmd
    assert cmd.endswith("postgres:17")


def test_connection_string_omits_the_password():
    assert (
        template_db.connection_string("agent_1")
        == "postgresql://postgres@localhost:5434/agent_1"
    )
