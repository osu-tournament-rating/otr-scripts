import shlex
from pathlib import Path

from lib.constants import buckets
from lib.scripts import db


def public_export_tokens() -> list[str]:
    return shlex.split(
        db._export_command(buckets.PUBLIC, Path("/tmp/otr-test-public-replica.gz"))
    )


def test_public_attributes_include_their_source_file_and_beatmap_foreign_keys():
    tokens = public_export_tokens()
    tables = {
        tokens[index + 1]
        for index, token in enumerate(tokens[:-1])
        if token == "--table"
    }

    assert {
        "public.beatmap_attributes",
        "public.beatmap_files",
        "public.beatmaps",
    } <= tables
    assert tables.isdisjoint(
        {
            "public.beatmap_attribute_jobs",
            "public.auth_accounts",
            "public.auth_sessions",
            "public.api_keys",
            "public.logs",
        }
    )


def test_public_export_keeps_full_schema_and_tolerates_new_tables_before_migration():
    tokens = public_export_tokens()

    assert tokens.index("--schema-only") < tokens.index("--data-only")
    assert tokens.index("--data-only") < tokens.index("--table")
    assert "--strict-names" not in tokens
    assert "--disable-triggers" in tokens
