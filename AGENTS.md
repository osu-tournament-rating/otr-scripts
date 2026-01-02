# AGENTS.md

## Repository Purpose

Infrastructure automation and operational scripts for the o!TR
(osu! Tournament Rating) platform. Handles database backup/archival,
API client generation, rating processor execution, and public data exports.

## Environment Setup

Scripts expect to run from the production server or with manual environment override.

```bash
# Copy secrets template and populate with actual values
cp src/env/secrets.template.env src/env/secrets.env
# Edit secrets.env with DATABASE_PASSWORD and RABBITMQ_URL
```

All .env files must end with a blank newline.

## Commands

All commands assume you're in `~/otr-scripts/src/`:

```bash
# Load environment (required before running any script)
source load-env.sh

# Override environment manually (local development)
ENV=staging source load-env.sh

# Database operations (production only)
bash db/archive-full.sh      # Full database backup to GCS
bash db/archive-dev.sh       # Dev replica (excludes sensitive data)
bash db/archive-public.sh    # Public replica (whitelisted tables only)
bash db/import-dump.sh <dump.gz> [container]  # Import database dump
bash db/disaster-recovery.sh # Restore latest dump from GCS

# Run rating processor
bash processor/otr-processor-job.sh

# Generate and publish API client (run from anywhere)
./update-api-client.sh
./update-api-client.sh --help
```

## Architecture

### Environment Configuration (src/env/)

Three-layer configuration loaded by `load-env.sh`:

1. `shared.env` - Common settings (DATABASE_CONTAINER, DATABASE_USER, GCS buckets)
2. `{staging,production}.env` - Environment-specific settings
3. `secrets.env` - Credentials (git-ignored)

Environment auto-detection from hostname: `otr-staging` → staging, `otr-prod` → production.

### Database Scripts (src/db/)

- `archive-full.sh` - Complete backup, production-only
- `archive-dev.sh` - Excludes auth tables, API keys, audit logs
- `archive-public.sh` - Only public-safe tables, adds GPG signature + checksum
- `import-dump.sh` - Utility to import gzipped dumps into Docker PostgreSQL
- `disaster-recovery.sh` - Downloads and restores latest GCS dump

### API Client Generation (src/update-api-client.sh)

Generates TypeScript API client from otr-api Swagger spec:

1. Runs `dotnet run --swagger-to-file` in API project
2. Runs `nswag run` to generate TypeScript client
3. Builds and formats generated code
4. Interactive prompts for npm version bump and publishing

Configurable paths via environment variables: `API_DIR`, `CLIENTS_DIR`, `TS_CLIENT_DIR`.

## Script Patterns

All scripts follow these conventions:

- `set -e` for immediate exit on error
- Source `load-env.sh` at the start
- Validate required environment variables before execution
- Production scripts check `$ENVIRONMENT == "production"` and refuse to run elsewhere
- Use `docker exec` for PostgreSQL operations
- Upload to GCS buckets specified in environment config
