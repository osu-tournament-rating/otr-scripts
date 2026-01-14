# otr-scripts

Infrastructure automation and operational scripts for the osu! Tournament Rating
(o!TR) platform. Handles database backup/archival, API client generation, rating
processor execution, and public data exports.

## Dependencies

- Docker
- Google Cloud SDK (gcloud)
- GPG (for public dump signatures)

### API Client Script

- .NET SDK
- Node.js & npm
- NSwag CLI

## Configuration

All `.env` files **must** end with a blank newline.

### Environment Variables

Scripts use a three-layer configuration system loaded by `load-env.sh`:

1. **Shared** (`src/env/shared.env`) - Common settings (database, GCS buckets)
2. **Environment-specific** (`src/env/{staging,production}.env`) - Environment settings
3. **Secrets** (`src/env/secrets.env`) - Credentials (git-ignored)

Environment auto-detection from hostname: `otr-staging` → staging, `otr-prod` →
production.

### Setting up Secrets

1. Copy the secrets template:

   ```bash
   cp src/env/secrets.template.env src/env/secrets.env
   ```

2. Populate with actual values:

   ```bash
   DATABASE_PASSWORD=your_actual_password_here
   RABBITMQ_URL=amqp://admin:admin@localhost:5672
   ```

3. Never commit `secrets.env` to version control.

### Loading Environment

Before running scripts, source the environment loader:

```bash
cd src
source load-env.sh
```

Scripts do this automatically. To manually override the environment:

```bash
ENV=staging source load-env.sh
```

## Scripts

### Database Operations (`src/db/`)

| Script | Description |
|--------|-------------|
| `archive-full.sh` | Complete backup (production-only), uploads to GCS |
| `archive-dev.sh` | Dev replica excluding sensitive data |
| `archive-public.sh` | Public replica with GPG signature + checksum |
| `import-dump.sh` | Import gzipped dump into Docker PostgreSQL |
| `disaster-recovery.sh` | Restore latest dump from GCS |

### Rating Processor (`src/processor/`)

| Script | Description |
|--------|-------------|
| `otr-processor-job.sh` | Execute otr-processor Docker container |

### API Client Generation (`src/update-api-client.sh`)

Generates TypeScript API client from otr-api Swagger spec:

1. Runs `dotnet run --swagger-to-file` in API project
2. Runs `nswag run` to generate TypeScript client
3. Builds and formats generated code
4. Interactive prompts for npm version bump and publishing

Configurable via environment variables: `API_DIR`, `CLIENTS_DIR`, `TS_CLIENT_DIR`.

```bash
./update-api-client.sh
./update-api-client.sh --help
```

### Public Data Export (`src/public-dump-web/`)

| Script | Description |
|--------|-------------|
| `generate-index.sh` | Generate HTML index page for public downloads |

## Data Protection

### Excluded from Dev Replica

`archive-dev.sh` exports complete schema but excludes data from these tables:

- `public.api_keys`
- `public.auth_accounts`
- `public.auth_sessions`
- `public.auth_users`
- `public.auth_verifications`
- `public.game_audits`
- `public.game_score_audits`
- `public.logs`
- `public.match_audits`
- `public.tournament_audits`

### Public Replica Whitelist

`archive-public.sh` only includes these tables:

- `drizzle.__drizzle_migrations`
- `public.beatmap_attributes`
- `public.beatmaps`
- `public.beatmapsets`
- `public.game_scores`
- `public.games`
- `public.join_beatmap_creators`
- `public.join_pooled_beatmaps`
- `public.matches`
- `public.player_osu_ruleset_data`
- `public.players`
- `public.tournaments`

### Terms of Use

Public replicas are provided for:

1. Testing or contributing to official o!TR repositories
2. Validating tournament usage by inspecting datasets

Permission for third-party applications is not implicitly granted. Contact Stage
for authorization. See `src/public-dump-web/terms-of-use.txt` for full terms.

## Command Reference

All commands assume you're in `~/otr-scripts/src/`:

```bash
# Load environment (required before running any script)
source load-env.sh

# Override environment manually
ENV=staging source load-env.sh

# Database operations (production-only)
bash db/archive-full.sh
bash db/archive-dev.sh
bash db/archive-public.sh
bash db/import-dump.sh <dump.gz> [container]
bash db/disaster-recovery.sh

# Run rating processor
bash processor/otr-processor-job.sh

# Generate and publish API client
./update-api-client.sh
```

## Script Patterns

All scripts follow these conventions:

- `set -e` for immediate exit on error
- Source `load-env.sh` at the start
- Validate required environment variables
- Production scripts check `$ENVIRONMENT == "production"`
- Use `docker exec` for PostgreSQL operations
- Upload to GCS buckets specified in environment config
