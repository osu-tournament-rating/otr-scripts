# Archive the current state of the db and upload to gcp
import itertools
import logging
import shlex
from datetime import datetime, timezone
from pathlib import Path
from lib.cli import ScriptArgs
from lib.config import config
from lib.constants import buckets
from lib.gcs import gcs_utils
from lib.public_html import generate_index
from lib.security import hash
import subprocess

logger = logging.getLogger(__name__)


# Include all objects in these schemas in public archives
public_schema_whitelist = [
    "drizzle",
]

# Include exactly these public-schema tables in public archives
public_table_whitelist = [
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

# Include all tables besides these in dev dumps (for internal dev use)
dev_blacklist = [
    "public.api_keys",
    "public.auth_accounts",
    "public.auth_sessions",
    "public.auth_users",
    "public.auth_verifications",
    "public.game_audits",
    "public.game_score_audits",
    "public.logs",
    "public.match_audits",
    "public.tournament_audits",
]


def _import(dump: Path) -> bool:
    """Import a local dump to the database"""
    if dump.suffix != ".gz":
        logger.error(f"Expected dump path to end with '.gz': {dump}")
        return False

    # Restore cannot happen if there are any active connections

    profile = " --profile node-exporter" if config.environment == "production" else ""

    stop_all = f"docker compose{profile} down"
    subprocess.run(stop_all, shell=True, cwd=config.otr_web_dir)

    start_db = f"docker compose{profile} up -d db"
    subprocess.run(start_db, shell=True, cwd=config.otr_web_dir)

    bash = f"psql -U {config.db_user} -d template1 -c 'DROP DATABASE IF EXISTS {config.db_name};' \
            && psql -U {config.db_user} -d template1 -c 'CREATE DATABASE {config.db_name};' \
            && psql -U {config.db_user} -d {config.db_name}"

    proc1 = subprocess.run(f"gunzip -c {dump}", shell=True, capture_output=True)

    if proc1.stderr:
        logger.error(f"gunzip produced errors: {proc1.stderr}")
        return False

    proc2 = subprocess.run(
        args=f'docker exec -i {config.db_container} bash -c "{bash}"',
        shell=True,
        input=proc1.stdout,
    )

    start_all = f"docker compose{profile} up -d"
    subprocess.run(start_all, shell=True, cwd=config.otr_web_dir)

    if proc2.stderr:
        logger.error(f"docker exec produced errors: {proc2.stderr}")
        return False

    remove_dumps()

    return True


def remove_dumps():
    cmd = f"rm {config.dump_dir}/*"
    subprocess.run(cmd, shell=True)


def _pg_dump_options(option: str, patterns: list[str]) -> list[str]:
    return list(
        itertools.chain.from_iterable((option, pattern) for pattern in patterns)
    )


def _pg_dump_command(options: list[str]) -> str:
    return shlex.join(
        [
            "docker",
            "exec",
            "-i",
            config.db_container,
            "pg_dump",
            "-c",
            "--if-exists",
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


def _export_command(replica: str, dest: Path) -> str:
    if replica == buckets.DEV:
        return _gzip_dump_command(
            [_pg_dump_command(_pg_dump_options("--exclude-table-data", dev_blacklist))],
            dest,
        )

    if replica == buckets.PUBLIC:
        # pg_dump ignores --schema when --table is used, so public exports need
        # separate streams for the whole drizzle schema and whitelisted tables.
        return _gzip_dump_command(
            [
                _pg_dump_command(_pg_dump_options("--schema", public_schema_whitelist)),
                _pg_dump_command(_pg_dump_options("--table", public_table_whitelist)),
            ],
            dest,
        )

    return _gzip_dump_command([_pg_dump_command([])], dest)


def _export(replica: str) -> tuple[bool, Path]:
    dump_file_format = datetime.now(timezone.utc).strftime(
        f"otr-{replica}-replica_%Y-%m-%d_%H_%M_%S.gz"
    )
    config.dump_dir.mkdir(parents=True, exist_ok=True)

    dest = config.dump_dir / dump_file_format

    cmd = _export_command(replica, dest)

    logger.info(f"Running subprocess {cmd}")

    result = subprocess.run(["bash", "-o", "pipefail", "-c", cmd])

    if result.returncode == 0:
        logger.info("Database archive creation succeeded")
        return True, dest
    else:
        logger.error("Database archive creation failed")
        return False, dest


def archive(args: ScriptArgs):
    bucket = args.archive_bucket
    if not bucket:
        raise Exception("Archive bucket must be populated")

    success, dump = _export(bucket)

    if not success:
        logger.error(f"Failed to export bucket to local path {dump}")
        return

    try:
        gcs_utils.upload(dump, bucket)

        if args.upload_hash:
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
        _import(args.recovery_src)
        return

    bucket = args.recovery_bucket
    if not bucket:
        raise Exception("Recovery bucket must be populated")

    # Download and import
    out_file = gcs_utils.download_latest(bucket, config.dump_dir)
    if not out_file:
        return

    _import(out_file)
