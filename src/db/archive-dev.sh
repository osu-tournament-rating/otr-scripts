#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Source environment variables
# shellcheck source=/dev/null
source "${HOME}/otr-scripts/src/load-env.sh"

# Check if running in production environment
if [ "$ENVIRONMENT" != "production" ]; then
  echo "Error: This script can only be run in production"
  echo "Current environment: $ENVIRONMENT"
  exit 1
fi

# === CONFIG ===
user="${DATABASE_USER}"
db="${DATABASE_NAME}"
container="${DATABASE_CONTAINER}"
date=$(date '+%Y_%m_%d_%H_%M_%S')
dest_folder="${DUMP_DESTINATION}"
dest_file="${dest_folder}/otr-dev-replica_${date}.gz"
# === CONFIG ===

# Validate required environment variables
if [ -z "${DATABASE_USER}" ]; then
  echo "Error: DATABASE_USER not defined in environment file"
  exit 1
fi

if [ -z "${DATABASE_NAME}" ]; then
  echo "Error: DATABASE_NAME not defined in environment file"
  exit 1
fi

if [ -z "${DATABASE_CONTAINER}" ]; then
  echo "Error: DATABASE_CONTAINER not defined in environment file"
  exit 1
fi

# Tables to exclude data from (but keep schema)
excluded_data_tables=(
  public.api_keys
  public.auth_accounts
  public.auth_sessions
  public.auth_users
  public.auth_verifications
  public.game_audits
  public.game_score_audits
  public.logs
  public.match_audits
  public.tournament_audits
)

# Build the --exclude-table-data arguments
exclude_data_args=""
for table in "${excluded_data_tables[@]}"; do
  exclude_data_args+=" --exclude-table-data=${table}"
done

# Check if DUMP_DESTINATION is defined
if [ -z "${DUMP_DESTINATION}" ]; then
  echo "Error: DUMP_DESTINATION not defined in environment file"
  exit 1
fi

# Check if GCS_DEV_BUCKET is defined
if [ -z "${GCS_DEV_BUCKET}" ]; then
  echo "Error: GCS_DEV_BUCKET not defined in environment file"
  exit 1
fi

# Ensure the destination directory exists
echo "Creating database dump..."
mkdir -p "${dest_folder}"

# Dump
{
  # Dump complete schema for all tables
  docker exec "${container}" pg_dump -s -c --if-exists -U "${user}" "${db}"
  # Dump data for all tables except the excluded ones
  # shellcheck disable=SC2086
  docker exec "${container}" pg_dump -a --disable-triggers ${exclude_data_args} -U "${user}" "${db}"
} | gzip >"${dest_file}"

echo "Database dump created at ${dest_file}"

# Copying to cloud storage
echo "Copying to cloud storage"
if gcloud storage cp "${dest_file}" "gs://${GCS_DEV_BUCKET}"; then
  echo "Files uploaded to Google Cloud Storage bucket!"
else
  echo "Failed to upload files to Google Cloud Storage bucket!" >&2
  exit 1
fi

# Cleanup
echo "Removing local dump file"
rm "${dest_folder}"/*.gz
echo "Cleared all *.gz files from ${dest_folder}"

echo "Script completed successfully."
