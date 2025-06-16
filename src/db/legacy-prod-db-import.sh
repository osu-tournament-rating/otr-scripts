#!/bin/bash

# Simple error handling - exit on any error
set -e

# Configuration
BUCKET_NAME="otr-prod-dumps"
DIR="/tmp/otr-dumps"
CONTAINER="b138239d97fa"

echo "Starting database sync process..."

# Get latest file from GCS bucket
echo "Fetching latest file from GCS bucket..."
LATEST_FILE=$(gcloud storage ls "gs://${BUCKET_NAME}" | sort | tail -n 1)
if [ -z "${LATEST_FILE}" ]; then
    echo "Error: No files found in bucket ${BUCKET_NAME}"
    exit 1
fi

# Extract filename from full path
FILENAME=$(basename "${LATEST_FILE}")
echo "Latest file identified: ${FILENAME}"

echo "Creating directory ${DIR}"

mkdir -p "${DIR}"

# Download the file
echo "Downloading file from GCS..."
gcloud storage cp "${LATEST_FILE}" "${DIR}"
if [ ! -f "${DIR}/${FILENAME}" ]; then
    echo "Error: File download failed"
    exit 1
fi

# Execute database commands on staging server
echo "Executing database commands on staging server..."
echo 'Starting container...'
docker start "${CONTAINER}"

echo 'Dropping public schema...'
docker exec "${CONTAINER}" psql -U postgres -d postgres -c 'DROP SCHEMA public CASCADE;'

echo 'Creating new public schema...'
docker exec "${CONTAINER}" psql -U postgres -d postgres -c 'CREATE SCHEMA public;'

echo 'Importing database dump...'
gunzip -c "${DIR}/${FILENAME}" | docker exec -i "${CONTAINER}" psql -U postgres -d postgres

echo 'Cleaning up temporary directory...'
rm -rf "${DIR}"

echo "Database sync process completed successfully!"

dotnet ef database update --project ~/Documents/code/git/otr-api/Database/Database.csproj --startup-project ~/Documents/code/git/otr-api/API/API.csproj --context Database.OtrContext

exit 0
