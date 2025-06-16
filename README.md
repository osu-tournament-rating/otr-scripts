# otr-scripts

Internal scripts used by the o!TR platform

## Dependencies

- Docker
- Google Cloud SDK (gcloud)

### API client script

- .NET SDK
- Node.js & npm
- NSwag CLI

## Configuration

Note: All .env files **must** end with a blank new line.

### Environment Variables

The scripts use a layered environment configuration system:

1. **Shared configuration** (`src/env/shared.env`) - Common settings across all environments
2. **Environment-specific configuration** (`src/env/{environment}.env`) - Settings specific to staging or production
3. **Secrets configuration** (`src/env/secrets.env`) - Sensitive values that should not be committed

### Setting up Secrets

1. Copy the secrets template file:

   ```bash
   cp src/env/secrets.template.env src/env/secrets.env
   ```

2. Edit `src/env/secrets.env` and populate with actual values:

   ```bash
   # Example:
   DATABASE_PASSWORD=your_actual_password_here
   ```

3. **Important**: Never commit `secrets.env` to version control

### Loading Environment Variables

Before running scripts, source the environment loader:

```bash
cd src
source load-env.sh
```

_Scripts are configured to do this automatically._

This will:

- Auto-detect your environment (staging/production) based on hostname
- Load shared configuration
- Load environment-specific configuration
- Load secrets

If auto-detection fails, you can manually set the environment:

```bash
ENV=staging source load-env.sh
```
