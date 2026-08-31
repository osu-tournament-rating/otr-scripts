"""Disposable Postgres container holding a template database.

Instances are created with `CREATE DATABASE ... TEMPLATE`, a file-level copy,
so an agent gets its own database without restoring a dump each time.
"""

import logging
import re
import shlex
import subprocess
import time
from pathlib import Path

from lib.cli import ScriptArgs
from lib.config import config
from lib.constants import buckets, scripts
from lib.gcs import gcs_utils

logger = logging.getLogger(__name__)

TEMPLATE = "otr_template"
IMAGE = "postgres:17"

reserved_names = {TEMPLATE, "postgres", "template0", "template1"}

_name = re.compile(r"^[a-z][a-z0-9_]{0,30}$")


def validate_name(name: str | None) -> str:
    if not name or not _name.match(name) or name in reserved_names:
        raise ValueError(
            f"Invalid instance name '{name}': expected ^[a-z][a-z0-9_]{{0,30}}$ "
            f"and not one of {', '.join(sorted(reserved_names))}"
        )

    return name


def guard():
    """Refuse to act on anything but the dedicated template container."""
    if config.template_db_port in (5432, 5433):
        raise RuntimeError(
            f"Template port {config.template_db_port} is reserved for other "
            "databases; set TEMPLATE_DB_PORT to a free port"
        )

    if config.template_db_container == config.db_container:
        raise RuntimeError(
            f"TEMPLATE_DB_CONTAINER '{config.template_db_container}' is the "
            "configured application database container"
        )


def psql_command(sql: str, db: str = "postgres") -> list[str]:
    return [
        "docker",
        "exec",
        "-i",
        config.template_db_container,
        "psql",
        "-U",
        config.template_db_user,
        "-d",
        db,
        "-Aqt",
        "--no-psqlrc",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        sql,
    ]


def run_command(cmd: list[str]) -> str | None:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        logger.error(f"{shlex.join(cmd)} failed: {result.stderr.strip()}")
        return None

    return result.stdout


def create_container_command() -> list[str]:
    return [
        "docker",
        "run",
        "-d",
        "--name",
        config.template_db_container,
        "-e",
        f"POSTGRES_USER={config.template_db_user}",
        "-e",
        f"POSTGRES_PASSWORD={config.template_db_password}",
        "-p",
        f"127.0.0.1:{config.template_db_port}:5432",
        "-v",
        f"{config.template_db_container}-data:/var/lib/postgresql/data",
        IMAGE,
    ]


def restore_command(dump: Path) -> list[str]:
    load = shlex.join(
        [
            "docker",
            "exec",
            "-i",
            config.template_db_container,
            "psql",
            "-U",
            config.template_db_user,
            "-d",
            TEMPLATE,
            "-v",
            "ON_ERROR_STOP=1",
            "--quiet",
        ]
    )

    return [
        "bash",
        "-o",
        "pipefail",
        "-c",
        f"gunzip -c {shlex.quote(str(dump))} | {load}",
    ]


def seed_steps(dump: Path) -> list[list[str]]:
    return [
        psql_command(
            f"UPDATE pg_database SET datistemplate = false WHERE datname = '{TEMPLATE}'"
        ),
        terminate_command(TEMPLATE),
        psql_command(f"DROP DATABASE IF EXISTS {TEMPLATE}"),
        psql_command(f"CREATE DATABASE {TEMPLATE}"),
        restore_command(dump),
        psql_command(
            f"UPDATE pg_database SET datistemplate = true WHERE datname = '{TEMPLATE}'"
        ),
    ]


def terminate_command(db: str) -> list[str]:
    return psql_command(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{db}' AND pid <> pg_backend_pid()"
    )


def create_steps(name: str) -> list[list[str]]:
    return [
        terminate_command(TEMPLATE),
        psql_command(f"CREATE DATABASE {name} TEMPLATE {TEMPLATE}"),
    ]


def drop_steps(name: str) -> list[list[str]]:
    return [terminate_command(name), psql_command(f"DROP DATABASE IF EXISTS {name}")]


def list_command() -> list[str]:
    return psql_command(
        "SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database "
        "WHERE datistemplate = false AND datname NOT IN "
        f"('postgres', '{TEMPLATE}') ORDER BY datname"
    )


def connection_string(name: str) -> str:
    return (
        f"postgresql://{config.template_db_user}:{config.template_db_password}"
        f"@localhost:{config.template_db_port}/{name}"
    )


def container_state() -> str | None:
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", config.template_db_container],
        capture_output=True,
        text=True,
        check=False,
    )

    return result.stdout.strip() if result.returncode == 0 else None


def wait_for_db(timeout: float = 120) -> bool:
    deadline = time.monotonic() + timeout

    while True:
        ready = subprocess.run(
            [
                "docker",
                "exec",
                config.template_db_container,
                "pg_isready",
                "-U",
                config.template_db_user,
            ],
            capture_output=True,
            check=False,
        )
        if ready.returncode == 0:
            return True
        if time.monotonic() >= deadline:
            logger.error(
                f"{config.template_db_container} not ready after {timeout:.0f}s"
            )
            return False
        time.sleep(1)


def ensure_container() -> bool:
    state = container_state()

    if state is None:
        logger.info(f"Creating container {config.template_db_container}")
        if run_command(create_container_command()) is None:
            return False
    elif state != "running":
        logger.info(f"Starting container {config.template_db_container}")
        if run_command(["docker", "start", config.template_db_container]) is None:
            return False

    return wait_for_db()


def template_exists() -> bool:
    out = run_command(
        psql_command(f"SELECT 1 FROM pg_database WHERE datname = '{TEMPLATE}'")
    )

    return bool(out and out.strip())


def seed(args: ScriptArgs) -> bool:
    if not ensure_container():
        return False

    dump = args.template_src
    if not dump:
        dump = gcs_utils.download_latest(buckets.DEV, config.dump_dir)
        if not dump:
            return False

    if dump.suffix != ".gz":
        logger.error(f"Expected dump path to end with '.gz': {dump}")
        return False

    started = time.monotonic()
    for step in seed_steps(dump):
        if subprocess.run(step, check=False).returncode != 0:
            logger.error(f"Seeding {TEMPLATE} failed: {shlex.join(step)}")
            return False

    logger.info(
        f"Seeded {TEMPLATE} from {dump.name} in {time.monotonic() - started:.0f}s"
    )
    return True


def create(name: str) -> bool:
    if not ensure_container():
        return False

    if not template_exists():
        logger.error(
            f"{TEMPLATE} does not exist; run "
            f"--script {scripts.TEMPLATE_DB} --template-action {scripts.SEED} first"
        )
        return False

    for step in create_steps(name):
        if run_command(step) is None:
            return False

    logger.info(f"Created {name}: {connection_string(name)}")
    return True


def drop(name: str) -> bool:
    if not ensure_container():
        return False

    for step in drop_steps(name):
        if run_command(step) is None:
            return False

    logger.info(f"Dropped {name}")
    return True


def list_instances() -> bool:
    if not ensure_container():
        return False

    out = run_command(list_command())
    if out is None:
        return False

    rows = [line for line in out.splitlines() if line.strip()]
    if not rows:
        logger.info("No instances")

    for row in rows:
        name, _, size = row.partition("|")
        logger.info(f"{name} ({size})")

    return True


def run(args: ScriptArgs) -> bool:
    guard()

    if args.template_action == scripts.SEED:
        return seed(args)

    if args.template_action == scripts.LIST:
        return list_instances()

    try:
        name = validate_name(args.template_name)
    except ValueError as e:
        logger.error(e)
        return False

    if args.template_action == scripts.CREATE:
        return create(name)

    if args.template_action == scripts.DROP:
        return drop(name)

    raise ValueError(f"Invalid template action '{args.template_action}'")
