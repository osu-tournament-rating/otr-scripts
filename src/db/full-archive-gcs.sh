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
date=$(date '+%y_%m_%d_%H_%M_%S')
dest_folder="${DUMP_DESTINATION}"
dest_file="${dest_folder}/postgres_${date}.gz"
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

if [ -z "${GCS_BUCKET}" ]; then
    echo "Error: GCS_BUCKET not defined in environment file"
    exit 1
fi

if [ -z "${DUMP_DESTINATION}" ]; then
    echo "Error: DUMP_DESTINATION not defined in environment file"
    exit 1
fi

# Ensure the destination directory exists
echo "Creating database dump..."
mkdir -p "${dest_folder}"

# Dump all tables (schema + data)
docker exec "${container}" pg_dump -c --if-exists -U "${user}" "${db}" | gzip >"${dest_file}"

echo "Database dump created at ${dest_file}"

# Copying to cloud storage
echo "Copying to cloud storage"
if gcloud storage cp "${dest_file}" "gs://${GCS_BUCKET}"; then
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
