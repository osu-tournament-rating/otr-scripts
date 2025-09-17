#!/bin/bash

set -e
set -o pipefail

# Source environment variables
# shellcheck source=/dev/null
source "${HOME}/otr-scripts/src/load-env.sh"

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
# Filter out non-object lines and capture the timestamp with the object URI,
# then sort by timestamp in descending order to find the most recent dump.
LATEST_ENTRY=$(gcloud storage ls -l "gs://${GCS_BUCKET}" \
    | awk 'NF >= 3 && $NF ~ /^gs:\/\// {print $(NF-1) " " $NF}' \
    | sort -k1,1r \
    | head -n1)

LATEST_FILE=$(awk '{print $2}' <<<"${LATEST_ENTRY}")

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
