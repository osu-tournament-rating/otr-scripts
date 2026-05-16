import logging
from pathlib import Path
from lib.constants import buckets
from lib.config import config
from lib.gcs import gcs_utils

logger = logging.getLogger(__name__)


def generate_index():
    # This will always be done for a public bucket
    bucket = gcs_utils.get_bucket_name(buckets.PUBLIC)

    terms = Path("src", "public-dump-web", "terms-of-use.txt").read_text()

    blobs = gcs_utils.list_all(bucket)
    link_template = f"https://storage.googleapis.com/{bucket}/{{}}"
    list_item_template = "<li><a href={}>{}</a></li>\n"

    blob_html = [
        list_item_template.format(link_template.format(b.name), b.name) for b in blobs
    ]

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Browse: o!TR Public Datasets</title>
        </head>
        <body>
            <h1>Terms of Use</h1>
            <p>{terms}</p>

            <h1>Files in {config.gcs_public_bucket}</h1>
            <ul>
                {blob_html}
            </ul>
        </body>
    </html>
    """

    index_loc = Path("src", "public-dump-web", "index.html")
    index_loc.write_text(html, encoding="utf-8")

    logger.info(f"Wrote new HTML to {index_loc}")
