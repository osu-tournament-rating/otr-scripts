#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Usage function
usage() {
    echo "Usage: $0 <dump-file> [container-name]"
    echo "  dump-file: Path to the .gz database dump file"
    echo "  container-name: Docker container name (default: otr-postgres)"
    echo ""
    echo "Example: $0 /path/to/dump.gz"
    echo "Example: $0 /path/to/dump.gz my-postgres-container"
    exit 1
}

# Check arguments
if [ $# -lt 1 ]; then
    usage
fi

DUMP_FILE="$1"
CONTAINER="${2:-otr-postgres}"
DB_USER="postgres"
TARGET_DB="postgres"

# Validate dump file exists
if [ ! -f "$DUMP_FILE" ]; then
    echo "Error: Dump file not found: $DUMP_FILE"
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "Error: Container '${CONTAINER}' is not running"
    echo "Available containers:"
    docker ps --format 'table {{.Names}}\t{{.Status}}'
    exit 1
fi

echo "Importing database dump into container: ${CONTAINER}"
echo "This will completely replace the existing database!"
echo ""

# Perform the import in a single pipeline
# Separate commands are used to avoid transaction issues
echo "Dropping and recreating database..."
gunzip -c "$DUMP_FILE" | docker exec -i "$CONTAINER" bash -c "
    psql -U $DB_USER -d template1 -c 'DROP DATABASE IF EXISTS $TARGET_DB;' && \
    psql -U $DB_USER -d template1 -c 'CREATE DATABASE $TARGET_DB;' && \
    psql -U $DB_USER -d $TARGET_DB
"

echo ""
echo "Database import completed successfully!"
