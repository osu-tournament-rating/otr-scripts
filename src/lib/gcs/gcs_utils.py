import logging
from pathlib import Path

from lib.config import config
from lib.constants import buckets
from lib.gcs.client import storage_client

logger = logging.getLogger(__name__)

def get_bucket_name(bucket: str):
    match bucket:
        case buckets.TEST:
            bucket_name = config.gcs_test_bucket
        case buckets.DEV:
            bucket_name = config.gcs_dev_bucket
        case buckets.PUBLIC:
            bucket_name = config.gcs_public_bucket
        case buckets.PROD:
            bucket_name = config.gcs_prod_bucket
        case _:
            raise Exception("Invalid bucket")
    return bucket_name


def upload(f: Path, bucket: str):
    """Upload a file to a bucket

    Args:
        f (Path): File to upload
        bucket (str): Bucket name
    """
    if not f.is_file():
        raise Exception(f"Cannot upload non-file {f}")

    bucket_name = get_bucket_name(bucket)

    logger.info(f"Uploading {f}")

    gcs_bucket = storage_client.bucket(bucket_name)
    blob = gcs_bucket.blob(f.name)
    blob.upload_from_filename(str(f))

    logger.info(f"Uploaded {blob} to {gcs_bucket}")
