#!/bin/bash

set -e

# Source environment variables
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/../load-env.sh"

# Configuration from environment variables
USER="${DATABASE_USER}"
DB="${DATABASE_NAME}"
CONTAINER="${DATABASE_CONTAINER}"
TEMP_DIR="${TEMP_DIR:-/tmp/otr-dumps}"

# Use GCS_BUCKET from environment file
if [ -z "${GCS_BUCKET}" ]; then
    echo "Error: GCS_BUCKET not defined in environment file"
    exit 1
fi

echo "Starting database restore process for ${ENVIRONMENT} environment..."

# Get latest file from GCS bucket
echo "Fetching latest file from GCS bucket ${GCS_BUCKET}..."
LATEST_FILE=$(gcloud storage ls "gs://${GCS_BUCKET}" | sort | tail -n 1)
if [ -z "${LATEST_FILE}" ]; then
    echo "Error: No files found in bucket ${GCS_BUCKET}"
    exit 1
fi

# Extract filename from full path
FILENAME=$(basename "${LATEST_FILE}")
echo "Latest file identified: ${FILENAME}"

# Create temporary directory
echo "Creating temporary directory ${TEMP_DIR}"
mkdir -p "${TEMP_DIR}"

# Download the file
echo "Downloading file from GCS..."
gcloud storage cp "${LATEST_FILE}" "${TEMP_DIR}"
if [ ! -f "${TEMP_DIR}/${FILENAME}" ]; then
    echo "Error: File download failed"
    exit 1
fi

# Execute database restoration
echo "Starting database restoration..."
docker exec -i "${CONTAINER}" dropdb -f --if-exists -U "${USER}" "${DB}"
docker exec -i "${CONTAINER}" createdb -U "${USER}" "${DB}"

echo "Importing database dump..."
gunzip -c "${TEMP_DIR}/${FILENAME}" | docker exec -i "${CONTAINER}" psql -U "${USER}" -d "${DB}"

# Cleanup
echo "Cleaning up temporary directory..."
rm -rf "${TEMP_DIR}"

echo "Database restoration completed successfully."
