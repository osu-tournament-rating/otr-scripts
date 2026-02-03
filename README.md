# otr-scripts

Infrastructure automation and operational scripts for the osu! Tournament Rating (o!TR) platform. Handles database backup/archival, rating processor execution, and public data exports.

## Dependencies

- Docker
- Google Cloud SDK (gcloud)
- GPG (for public dump signatures)

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

### Public Data Export (`src/public-dump-web/`)

| Script | Description |
|--------|-------------|
| `generate-index.sh` | Generate HTML index page for public downloads |

## Data Protection

- Inspect `src/db/archive-public.sh` to see the full list of tables included in the dump.
- Inspect `src/db/archive-dev.sh` to see which tables are excluded from dumps provided to devs on the team.

### Terms of Use

See `src/public-dump-web/terms-of-use.txt`.
