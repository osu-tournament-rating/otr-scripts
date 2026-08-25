import os
import shlex
from pathlib import Path
from types import SimpleNamespace

from lib.gcs import gcs_utils
from lib.scripts import db

OLDER = "otr-dev-replica_2026-08-20T12:00:00Z.gz"
KEEP = "otr-dev-replica_2026-08-24T12:00:00Z.gz"
NEWER = "otr-dev-replica_2026-08-25T12:00:00Z.gz"


def touch(directory: Path, *names: str) -> list[Path]:
    paths = [directory / name for name in names]
    for path in paths:
        path.write_bytes(b"")
    return paths


def record_runs(monkeypatch, fail_on: str | None = None) -> list:
    commands = []

    def run(cmd, **kwargs):
        commands.append(cmd)
        text = cmd if isinstance(cmd, str) else shlex.join(cmd)
        return SimpleNamespace(returncode=1 if fail_on and fail_on in text else 0)

    monkeypatch.setattr(db.subprocess, "run", run)
    return commands


def shell_commands(commands: list) -> list[str]:
    return [cmd for cmd in commands if isinstance(cmd, str)]


def test_prune_removes_only_older_archives_of_the_same_kind(tmp_path):
    touch(
        tmp_path,
        OLDER,
        KEEP,
        NEWER,
        f"{NEWER}.123.part",
        "otr-public-replica_2026-08-20T12:00:00Z.gz",
    )

    db.prune_dumps(tmp_path / KEEP)

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        KEEP,
        NEWER,
        f"{NEWER}.123.part",
        "otr-public-replica_2026-08-20T12:00:00Z.gz",
    ]


def test_restore_steps_target_only_the_configured_database():
    terminate, drop, create, load = db._restore_steps(Path("/dumps/a b.gz"))

    assert "datname = 'otr_test' AND pid <> pg_backend_pid()" in terminate[-1]
    for step in (terminate, drop, create):
        assert step[step.index("-d") + 1] == "template1"
    assert load[:4] == ["bash", "-o", "pipefail", "-c"]
    assert load[-1].startswith("gunzip -c '/dumps/a b.gz' | docker exec -i otr-test-db psql")
    assert "-d otr_test -v ON_ERROR_STOP=1 --quiet" in load[-1]


def test_db_only_restores_without_restarting_the_container(monkeypatch):
    commands = record_runs(monkeypatch)

    assert db._import(Path(f"/dumps/{KEEP}"), db_only=True) is True

    assert shell_commands(commands) == ["docker compose up -d db"]
    assert commands[1][:4] == ["docker", "exec", "otr-test-db", "pg_isready"]
    assert len(commands) == 6


def test_failed_load_fails_the_import(monkeypatch):
    record_runs(monkeypatch, fail_on="pipefail")

    assert db._import(Path(f"/dumps/{KEEP}"), db_only=True) is False


def test_full_restart_brings_the_stack_back_after_a_failure(monkeypatch):
    commands = record_runs(monkeypatch, fail_on="DROP DATABASE")

    assert db._import(Path(f"/dumps/{KEEP}")) is False

    assert shell_commands(commands) == [
        "docker compose down",
        "docker compose up -d db",
        "docker compose up -d",
    ]
    assert not any("CREATE DATABASE" in shlex.join(cmd) for cmd in commands[1:-1])


def test_recovery_prunes_only_after_a_successful_restore(monkeypatch, tmp_path):
    older, keep = touch(tmp_path, OLDER, KEEP)
    args = SimpleNamespace(recovery_src=None, recovery_bucket="dev", db_only=True)
    monkeypatch.setattr(db.gcs_utils, "download_latest", lambda bucket, out_dir: keep)

    monkeypatch.setattr(db, "_import", lambda dump, db_only: False)
    assert db.recovery(args) is False
    assert older.exists()

    monkeypatch.setattr(db, "_import", lambda dump, db_only: True)
    assert db.recovery(args) is True
    assert not older.exists()
    assert keep.exists()


def fake_storage(monkeypatch, download):
    client = SimpleNamespace(
        list_blobs=lambda bucket: [SimpleNamespace(name=KEEP)],
        download_blob_to_file=download,
    )
    monkeypatch.setattr(gcs_utils, "storage_client", client)


def test_download_writes_to_a_temporary_name_then_renames(monkeypatch, tmp_path):
    seen = []

    def download(blob, f):
        seen.append(Path(f.name).name)
        f.write(b"gz")

    fake_storage(monkeypatch, download)

    assert gcs_utils.download_latest("dev", tmp_path) == tmp_path / KEEP
    assert seen == [f"{KEEP}.{os.getpid()}.part"]
    assert [path.name for path in tmp_path.iterdir()] == [KEEP]


def test_failed_download_leaves_nothing_behind(monkeypatch, tmp_path):
    def download(blob, f):
        f.write(b"partial")
        raise OSError("connection reset")

    fake_storage(monkeypatch, download)

    assert gcs_utils.download_latest("dev", tmp_path) is None
    assert list(tmp_path.iterdir()) == []
