# Archive the current state of the db and upload to gcp
import itertools
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal
from lib.config import config
from lib.exec import run
from google.cloud.storage import Bucket
from google.cloud.storage import transfer_manager
from lib.gcp.client import storage_client

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
    if dump.suffix != ".gz":
        logger.error(f"Expected dump path to end with '.gz': {dump}")
        return False

    bash = f"psql -U {config.db_user} -d template1 -c 'DROP DATABASE IF EXISTS {config.db_name};' \
            && psql -U {config.db_user} -d template1 -c 'CREATE DATABASE {config.db_name};' \
            && psql -U {config.db_user} -d {config.db_name}"

    cmd: list[str] = (
        f'gunzip -c {dump} | docker exec -i {config.db_container} bash -c "{bash}"'.split()
    )

    return run(cmd)


def _export(replica: Literal["dev", "public", "production"]) -> tuple[bool, Path]:
    dump_file_format = datetime.now().strftime(
        f"otr-{replica}-replica_%Y-%m_%d_%H_%M_%S.gz"
    )
    dest = Path(config.dump_dir, dump_file_format)

    dev_excludes = [["--exclude-table-data", x] for x in dev_blacklist]
    public_includes = [["--table", x] for x in public_whitelist]

    cmd = (
        f"docker exec {config.db_container} pg_dump -c --if-exists -U {config.db_user} "
    )

    # cmd = [
    #     "docker",
    #     "exec",
    #     config.db_container,
    #     "'pg_dump",
    #     "-c",
    #     "--if-exists",
    #     "-U",
    #     config.db_user,
    # ]

    if replica == "dev":
        cmd += " ".join(itertools.chain.from_iterable(dev_excludes))
    elif replica == "public":
        cmd += " ".join(itertools.chain.from_iterable(public_includes))

    cmd += f" {config.db_name} | gzip > {dest}"

    logger.info(f"Running subprocess [{cmd}]")

    result = run([cmd])

    return result, dest


def _upload(dump: Path, replica: Literal["dev", "public", "production"]):
    """Upload a dump to GCP"""

    match replica:
        case "dev":
            bucket_name = config.gcs_dev_bucket
        case "public":
            bucket_name = config.gcs_public_bucket
        case "production":
            bucket_name = config.gcs_prod_bucket

    logger.info(f"Uploading {dump}")

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(dump.name)
    blob.upload_from_filename(str(dump))

    logger.info(f"Uploaded {blob} to {bucket}")


def _export_and_upload(replica: Literal["dev", "public", "production"]):
    success, dump = _export(replica)

    if not success:
        logger.error("Replica export failed, aborting upload")
        return

    try:
        _upload(dump, replica)
    except Exception:
        logger.exception(f"Error occurred during upload of {dump} to GCS bucket")


def dev_archive():
    _export_and_upload("dev")


def public_archive():
    _export_and_upload("public")
    # TODO: Rebuild HTML


def prod_archive():
    _export_and_upload("production")
