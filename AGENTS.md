# otr-scripts agent guidance

Run commands from the repository root with Python 3.14 and `uv`.

- `archive`, `recovery`, and `processor` are live-infrastructure operations.
  Never run them, upload archives, publish indexes, or deploy to test a code
  change. When one is required, stop and wait for manual intervention.
- `.env` holds credentials and infrastructure paths. `lib.config` loads it at
  import, so every command needs a complete configuration. Never commit it or
  log secret values.
- Bucket names and table inclusion policy live in their existing constants and
  `lib/scripts/db.py`; do not duplicate them.

## Commands

- Setup: `uv venv --python 3.14`, `uv pip install .` (`'.[e2e]'` only for
  external tests), copy `.env.example` to `.env`.
- `uv run python src/main.py --script <operation> [options]`. `--script`
  accepts several operations and runs them in order.
- Checks: `ruff check src tests`, `python -m compileall -q src`,
  `python -m pytest --collect-only tests`. Exercise the CLI with `--help` or
  invalid arguments, never a valid operational invocation.
- `python -m pytest -m e2e tests/e2e` needs Docker and GCS credentials and
  imports the latest public archive into an isolated `postgres:17` container.
  Run it only when explicitly validating that archive.

## Operations

- `archive --archive-bucket <test|dev|public|production>` dumps and uploads.
  Public archives publish a SHA256 file, contain the full schema but only
  whitelisted data, and refresh the HTML index; dev excludes sensitive tables;
  production and test are full dumps. `--upload-hash` adds the hash to the
  other buckets.
- `recovery --recovery-bucket <bucket>` or `--recovery-src <path.gz>` (mutually
  exclusive) stops services, drops and recreates the database, and imports.
  Only older archives of the same kind are removed from `DUMP_DIR`. `--db-only`
  restarts only the database container and is for local development.
- `processor` pulls `stagecodes/otr-processor:<TAG>` and runs it with host
  networking against the configured PostgreSQL and RabbitMQ.
- `refresh-index` writes the archive index beneath `PUBLIC_HTML_DIR`.
- Confirm `ENVIRONMENT`, `TAG`, database container and name, web directory,
  bucket mapping, and RabbitMQ URL before any live operation.

## Code

- CLI contract in `src/lib/cli.py`, configuration in `src/lib/config.py`,
  operations in `src/lib/`.
- Review schema changes against the public whitelist and dev blacklist so
  credentials, audit records, and logs never enter exports.
- Prefer argument lists for subprocesses; quote paths and preserve upstream
  failures when a shell pipeline is unavoidable.
