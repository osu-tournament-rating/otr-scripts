# Archive the current state of the db and upload to gcp
import itertools
import logging
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lib.cli import ScriptArgs
from lib.config import config
from lib.constants import buckets
from lib.gcs import gcs_utils
from lib.public_html import generate_index
from lib.security import hash

logger = logging.getLogger(__name__)


# Include data for exactly these tables in public archives
public_data_table_whitelist = [
    "drizzle.__drizzle_migrations",
    "public.beatmap_attributes",
    "public.beatmaps",
    "public.beatmapsets",
    "public.game_scores",
    "public.games",
    "public.join_beatmap_creators",
    "public.join_pooled_beatmaps",
    "public.matches",
    "public.player_osu_ruleset_data",
    "public.players",
    "public.tournaments",
]

# Dev archives mirror production row for row. These columns are credentials,
# not data; auth_accounts holds live osu! OAuth tokens for accounts o!TR does
# not control.
dev_secret_columns = {
    "public.api_keys": ("key",),
    "public.auth_accounts": (
        "access_token",
        "refresh_token",
        "id_token",
        "password",
    ),
    "public.auth_sessions": ("token",),
    "public.auth_verifications": ("value",),
    "public.o_auth_clients": ("secret",),
}

# Redacted values are text keyed on the row id, keeping NOT NULL and UNIQUE.
_redactable_types = {"text", "character varying", "character"}


@dataclass(frozen=True)
class Column:
    name: str
    data_type: str


def _import(dump: Path, db_only: bool = False) -> bool:
    """Import a local dump to the database

    Args:
        dump: Path to the gzipped database dump to restore.
        db_only: When True, only stop and start the database container instead
            of restarting the entire docker-compose stack. Useful for local dev
            where tearing down the whole stack is undesirable.
    """
    if dump.suffix != ".gz":
        logger.error(f"Expected dump path to end with '.gz': {dump}")
        return False

    # Restore cannot happen if there are any active connections

    profile = " --profile node-exporter" if config.environment == "production" else ""

    stop = (
        f"docker compose{profile} stop db"
        if db_only
        else f"docker compose{profile} down"
    )
    subprocess.run(stop, shell=True, cwd=config.otr_web_dir, check=False)

    start_db = f"docker compose{profile} up -d db"
    subprocess.run(start_db, shell=True, cwd=config.otr_web_dir, check=False)

    bash = f"psql -U {config.db_user} -d template1 -c 'DROP DATABASE IF EXISTS {config.db_name};' \
            && psql -U {config.db_user} -d template1 -c 'CREATE DATABASE {config.db_name};' \
            && psql -U {config.db_user} -d {config.db_name}"

    proc1 = subprocess.run(
        f"gunzip -c {dump}", shell=True, capture_output=True, check=False
    )

    if proc1.stderr:
        logger.error(f"gunzip produced errors: {proc1.stderr}")
        return False

    proc2 = subprocess.run(
        args=f'docker exec -i {config.db_container} bash -c "{bash}"',
        shell=True,
        input=proc1.stdout,
        check=False,
    )

    if not db_only:
        start_all = f"docker compose{profile} up -d"
        subprocess.run(start_all, shell=True, cwd=config.otr_web_dir, check=False)

    if proc2.stderr:
        logger.error(f"docker exec produced errors: {proc2.stderr}")
        return False

    remove_dumps()

    return True


def remove_dumps():
    cmd = f"rm {config.dump_dir}/*"
    subprocess.run(cmd, shell=True, check=False)


def _pg_dump_options(option: str, patterns: list[str]) -> list[str]:
    return list(
        itertools.chain.from_iterable((option, pattern) for pattern in patterns)
    )


def _pg_dump_command(options: list[str], clean: bool = True) -> str:
    clean_options = ["-c", "--if-exists"] if clean else []
    return shlex.join(
        [
            "docker",
            "exec",
            "-i",
            config.db_container,
            "pg_dump",
            *clean_options,
            "-U",
            config.db_user,
            *options,
            "-d",
            config.db_name,
        ]
    )


def _gzip_dump_command(dump_commands: list[str], dest: Path) -> str:
    if len(dump_commands) == 1:
        dump_command = dump_commands[0]
    else:
        dump_command = "{ " + " && ".join(dump_commands) + "; }"

    return f"{dump_command} | gzip > {shlex.quote(str(dest))}"


_identifier = re.compile(r"^[a-z_][a-z0-9_]*$")


def _split_table(table: str) -> tuple[str, str]:
    """Split a qualified name, rejecting anything not safe to inline into SQL."""
    schema, _, name = table.partition(".")

    if not _identifier.match(schema) or not _identifier.match(name):
        raise RuntimeError(f"Unsupported table name: {table}")

    return schema, name


def _psql_command(sql: str) -> list[str]:
    return [
        "docker",
        "exec",
        "-i",
        config.db_container,
        "psql",
        "-U",
        config.db_user,
        "-d",
        config.db_name,
        "-Aqt",
        "--no-psqlrc",
        "-c",
        sql,
    ]


def _table_columns(table: str) -> list[Column]:
    """Read a table's COPY-able columns, in ordinal order, from the database."""
    schema, name = _split_table(table)

    sql = (
        "SELECT column_name, data_type FROM information_schema.columns "
        f"WHERE table_schema = '{schema}' AND table_name = '{name}' "
        "AND is_generated <> 'ALWAYS' ORDER BY ordinal_position"
    )

    result = subprocess.run(
        _psql_command(sql),
        capture_output=True,
        text=True,
        check=True,
    )

    columns = [
        Column(*line.split("|", 1)) for line in result.stdout.splitlines() if line.strip()
    ]

    if not columns:
        raise RuntimeError(f"No columns found for {table}; is the schema applied?")

    return columns


def _redacted_select(column: Column) -> str:
    if column.data_type not in _redactable_types:
        raise RuntimeError(
            f"Cannot redact {column.name}: expected a text column, got {column.data_type}"
        )

    return (
        f'CASE WHEN "{column.name}" IS NULL THEN NULL '
        f"ELSE 'redacted:{column.name}:' || \"id\" END"
    )


def _redacted_copy_command(table: str, columns: list[Column]) -> str:
    _split_table(table)
    secrets = dev_secret_columns[table]

    known = {column.name for column in columns}
    missing = [secret for secret in secrets if secret not in known]
    if missing:
        raise RuntimeError(f"{table} is missing redacted columns: {', '.join(missing)}")
    if "id" not in known:
        raise RuntimeError(f"{table} has no id column to key redacted values on")

    selected = ", ".join(
        _redacted_select(column) if column.name in secrets else f'"{column.name}"'
        for column in columns
    )
    column_list = ", ".join(f'"{column.name}"' for column in columns)

    header = shlex.join(["printf", "%s\\n", f"COPY {table} ({column_list}) FROM stdin;"])
    rows = shlex.join(_psql_command(f"COPY (SELECT {selected} FROM {table}) TO STDOUT"))
    terminator = shlex.join(["printf", "%s\\n", "\\."])

    return f"{{ {header} && {rows} && {terminator}; }}"


def _dev_export_command(columns_by_table: dict[str, list[Column]], dest: Path) -> str:
    # Dump by section so the redacted rows land alongside the rest of the data,
    # before post-data adds the foreign keys that would validate against them.
    tables = list(dev_secret_columns)

    return _gzip_dump_command(
        [
            _pg_dump_command(["--section=pre-data"]),
            _pg_dump_command(
                [
                    "--section=data",
                    *_pg_dump_options("--exclude-table-data", tables),
                ],
                clean=False,
            ),
            *(_redacted_copy_command(table, columns_by_table[table]) for table in tables),
            _pg_dump_command(["--section=post-data"], clean=False),
        ],
        dest,
    )


def _export_command(replica: str, dest: Path) -> str:
    if replica == buckets.DEV:
        return _dev_export_command(
            {table: _table_columns(table) for table in dev_secret_columns}, dest
        )

    if replica == buckets.PUBLIC:
        # Match the original public archive script: dump the full schema so
        # extensions, functions, triggers, and FK targets exist, then include
        # data only for public-safe tables.
        return _gzip_dump_command(
            [
                _pg_dump_command(["--schema-only"]),
                _pg_dump_command(
                    [
                        "--data-only",
                        "--disable-triggers",
                        *_pg_dump_options("--table", public_data_table_whitelist),
                    ],
                    clean=False,
                ),
            ],
            dest,
        )

    return _gzip_dump_command([_pg_dump_command([])], dest)


def _export(replica: str) -> tuple[bool, Path]:
    dump_file_format = datetime.now(UTC).strftime(
        f"otr-{replica}-replica_%Y-%m-%dT%H:%M:%SZ.gz"
    )
    config.dump_dir.mkdir(parents=True, exist_ok=True)

    dest = config.dump_dir / dump_file_format

    cmd = _export_command(replica, dest)

    logger.info(f"Running subprocess {cmd}")

    result = subprocess.run(["bash", "-o", "pipefail", "-c", cmd], check=False)

    if result.returncode == 0:
        logger.info("Database archive creation succeeded")
        return True, dest
    else:
        logger.error("Database archive creation failed")
        return False, dest


def archive(args: ScriptArgs):
    bucket = args.archive_bucket
    if not bucket:
        raise ValueError("Archive bucket must be populated")

    success, dump = _export(bucket)

    if not success:
        logger.error(f"Failed to export bucket to local path {dump}")
        return

    try:
        gcs_utils.upload(dump, bucket)

        # Public replicas are always published with a checksum so consumers
        # (including otr-replay) can verify their downloads.
        if args.upload_hash or bucket == buckets.PUBLIC:
            # Upload sha256
            hash_loc = hash(dump)
            gcs_utils.upload(hash_loc, bucket)

            # Remove after upload
            hash_loc.unlink()

        if args.archive_bucket == buckets.PUBLIC:
            # Refresh the html
            generate_index()

        remove_dumps()

    except Exception:
        logger.exception(f"Error occurred during upload of {dump} to GCS bucket")


def recovery(args: ScriptArgs):
    if args.recovery_src:
        # Just import this local dump, no GCS connection needed
        _import(args.recovery_src, db_only=args.db_only)
        return

    bucket = args.recovery_bucket
    if not bucket:
        raise ValueError("Recovery bucket must be populated")

    # Download and import
    out_file = gcs_utils.download_latest(bucket, config.dump_dir)
    if not out_file:
        return

    _import(out_file, db_only=args.db_only)
