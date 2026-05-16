import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    tag: str
    dump_dir: Path
    public_html_dir: Path
    db_port: int
    db_container: str
    db_user: str
    db_name: str
    db_password: str
    gcs_test_bucket: str
    gcs_dev_bucket: str
    gcs_public_bucket: str
    gcs_prod_bucket: str
    gcs_sa_json_path: Path
    rabbitmq_url: str


def _env_or_throw(key: str) -> str:
    var = os.getenv(key)
    if not var:
        raise EnvironmentError(f"Expected environment var '{key}' to be set")

    return var


def init() -> Config:
    if not load_dotenv():
        raise FileNotFoundError("Missing .env")

    return Config(
        _env_or_throw("TAG"),
        Path(_env_or_throw("DUMP_DIR")).expanduser(),
        Path(_env_or_throw("PUBLIC_HTML_DIR")).expanduser(),
        int(_env_or_throw("DB_PORT")),
        _env_or_throw("DB_CONTAINER"),
        _env_or_throw("DB_USER"),
        _env_or_throw("DB_NAME"),
        _env_or_throw("DB_PASSWORD"),
        _env_or_throw("GCS_TEST_BUCKET"),
        _env_or_throw("GCS_DEV_BUCKET"),
        _env_or_throw("GCS_PUBLIC_BUCKET"),
        _env_or_throw("GCS_PROD_BUCKET"),
        Path(_env_or_throw("GCS_SA_JSON_PATH")),
        _env_or_throw("RABBITMQ_URL"),
    )


config = init()
