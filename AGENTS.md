# AGENTS.md

## Repository purpose

This repository contains Python operational tooling for the osu! Tournament
Rating platform. It creates and restores PostgreSQL archives, runs the rating
processor image, and regenerates the public archive index.

## Runtime and setup

- Use Python 3.14 and `uv` from the repository root.
- Create the environment with `uv venv --python 3.14` and install the project
  with `uv pip install .`. Install `'.[e2e]'` only when running external tests.
- Copy `.env.example` to `.env` and populate every required setting before
  invoking the CLI. `.env` contains credentials and local infrastructure paths;
  never commit it or log secret values.
- `lib.config` loads `.env` during import. Even commands that do not obviously
  use every setting require a complete configuration.

## CLI and architecture

Invoke operations from the repository root with:

```bash
uv run python src/main.py --script <operation> [options]
```

`--script` accepts one or more operations and runs them in the supplied order:

- `archive --archive-bucket <test|dev|public|production>` creates a gzipped
  database archive and uploads it to the mapped Google Cloud Storage bucket.
  Public archives always publish a SHA256 file alongside the archive;
  `--upload-hash` extends that to the other buckets. Public archives include the
  full schema but data only from the explicit whitelist in `lib/scripts/db.py`;
  dev archives mirror production row for row with the credential columns in
  `dev_secret_columns` redacted; production and test archives are full dumps. A
  public upload also refreshes the HTML index.
- `recovery --recovery-bucket <bucket>` downloads and restores the newest archive
  from that bucket. `--recovery-src <path.gz>` restores a local archive instead;
  these source options are mutually exclusive.
- `processor` pulls `stagecodes/otr-processor:<TAG>` and runs it against the
  configured PostgreSQL and RabbitMQ services using host networking.
- `refresh-index` lists the public bucket and writes the archive index beneath
  `PUBLIC_HTML_DIR`.

The CLI contract lives in `src/lib/cli.py`, configuration in
`src/lib/config.py`, and operation implementations in `src/lib/`. Keep bucket
names and table inclusion policy in their existing constants and database
modules rather than duplicating them elsewhere.

## Operational safety

- Treat `archive`, `recovery`, and `processor` as live-infrastructure operations.
  Confirm `ENVIRONMENT`, `TAG`, database container/name, o!TR web directory, GCS
  bucket mapping, and RabbitMQ URL before running them.
- Recovery is destructive: it stops services, drops and recreates the configured
  database, and imports the dump. A downloaded archive is retained after a
  successful restore; only older archives of the same kind are removed from
  `DUMP_DIR`. Never run recovery as validation against a populated environment.
- By default, recovery takes down and restarts the full Compose stack. Pass
  `--db-only` only for local development when recovery should stop and start the
  database container without restarting the rest of the stack.
- Keep the public data whitelist deliberately narrow. Review schema changes
  against it so credentials, audit records, logs, and other private data cannot
  enter public exports.
- Dev archives carry every table and row, including audits, logs, and real user
  records, so treat them as production data and keep them on trusted
  infrastructure. Only `dev_secret_columns` is withheld: session and API key
  material, and the osu! OAuth tokens in `auth_accounts`, whose blast radius
  reaches accounts o!TR does not control. Add any new secret-bearing column to
  that map; the export fails if a listed column is missing or is not text.
- Use argument lists for subprocesses where practical. When a pipeline or shell
  expansion is required, quote paths and preserve upstream command failures.
- Do not run deployments, upload archives, restore databases, publish indexes, or
  start the processor merely to test a code change.
- When a potentially destructive operation is required, STOP and wait for manual
  intervention before proceeding.

## Validation

- Run `ruff check src tests` for static checks.
- Run `python -m compileall -q src` for a syntax/import compilation check.
- Run `python -m pytest --collect-only tests` to verify test discovery without
  contacting external services.
- Run `python -m pytest tests -m 'not e2e'` for the export unit tests. They stub
  `lib.config` and `lib.gcs.client`, so they need neither `.env` nor GCS.
- External tests require Docker, and the public archive test also needs GCS
  credentials. Run `python -m pytest -m e2e tests/e2e` only when explicitly
  validating archives; both tests use isolated `postgres:17` containers, never
  the configured application database. `test_dev_replica_archive.py` seeds known
  credential values, exports a dev replica, and fails if any reaches the
  archive.
- Exercise CLI validation with `--help` or invalid argument combinations. Avoid
  a valid operational invocation unless its external effects are intended.

## Git conventions

```text
Branch: <short-kebab-case-description>

Commit:
<Imperative verb> <specific outcome>
(#<issue>)  # optional
```

- Branch names use two to five meaningful lowercase kebab-case terms, such as
  `agent-skills-refactor`, `rating-decay-window`, or `player-layout-fix`.
- Do not require `feature/`, `fix/`, `hotfix/`, `chore/`, usernames, vendors, or
  issue numbers.
- Tool-generated, Dependabot, upstream-sync, and scratch-worktree branches are
  exceptions.
- Commit subjects use sentence case and imperative mood, preferably at most 72
  characters, without a trailing period or Conventional Commit prefix.
- Avoid opaque subjects such as `fmt`, `prettier`, `cleanup`, or `(wip)`.
- Let GitHub add pull request numbers and merge metadata.
