# Archive the current state of the db and upload to gcp
import itertools
import logging
from datetime import datetime
from pathlib import Path
from lib.cli import ScriptArgs
from lib.config import config
from lib.constants import buckets
from lib.gcs import gcs_utils
from lib.public_html import generate_index
from lib.security import hash
import subprocess

logger = logging.getLogger(__name__)


# Include exactly these tables in public archives
public_whitelist = [
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
    stop_start = f"docker stop {config.db_container} || true && docker start {config.db_container} || true"
    subprocess.run(stop_start, shell=True)

    bash = f"psql -U {config.db_user} -d template1 -c 'DROP DATABASE IF EXISTS {config.db_name};' \
            && psql -U {config.db_user} -d template1 -c 'CREATE DATABASE {config.db_name};' \
            && psql -U {config.db_user} -d {config.db_name}"

    proc1 = subprocess.run(f"gunzip -c {dump}", capture_output=True, shell=True)

    if proc1.stderr:
        logger.error(f"gunzip produced errors: {proc1.stderr}")
        return False

    proc2 = subprocess.run(
        args=f'docker exec -i {config.db_container} bash -c "{bash}"',
        shell=True,
        input=proc1.stdout,
    )

    if proc2.stderr:
        logger.error(f"docker exec produced errors: {proc2.stderr}")
        return False

    return True


def _export(replica: str) -> tuple[bool, Path]:
    dump_file_format = datetime.now().strftime(
        f"otr-{replica}-replica_%Y-%m-%d_%H_%M_%S.gz"
    )
    config.dump_dir.mkdir(parents=True, exist_ok=True)

    dest = config.dump_dir / dump_file_format

    dev_excludes = [["--exclude-table-data", x] for x in dev_blacklist]
    public_includes = [["--table", x] for x in public_whitelist]

    cmd = f"docker exec -i {config.db_container} pg_dump -c --if-exists -U {config.db_user} "

    if replica == buckets.DEV:
        cmd += " ".join(itertools.chain.from_iterable(dev_excludes))
    elif replica == buckets.PUBLIC:
        cmd += " ".join(itertools.chain.from_iterable(public_includes))

    cmd = cmd.strip()
    cmd += f" -d {config.db_name} | gzip > {dest}"

    logger.info(f"Running subprocess {cmd}")

    result = subprocess.run(cmd, shell=True)

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

        if args.archive_bucket == buckets.PUBLIC:
            # Refresh the html
            generate_index()

    except Exception:
        logger.exception(f"Error occurred during upload of {dump} to GCS bucket")


def recovery(args: ScriptArgs):
    bucket = args.recovery_bucket
    if not bucket:
        raise Exception("Recovery bucket must be populated")

    if args.recovery_src:
        # Just import this dump
        _import(args.recovery_src)
    else:
        # Download and import
        out_file = gcs_utils.download_latest(bucket, config.dump_dir)
        if not out_file:
            return

        _import(out_file)
