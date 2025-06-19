#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Source environment variables
# shellcheck source=/dev/null
source "${HOME}/otr-scripts/src/load-env.sh"

# Validate required environment variables
if [ -z "${GCS_PUBLIC_BUCKET}" ]; then
    echo "Error: GCS_PUBLIC_BUCKET not defined in environment file"
    exit 1
fi

# Set variables from environment
BUCKET_NAME="${GCS_PUBLIC_BUCKET}"
WEB_ROOT="${HOME}/otr-scripts/src/public-dump-web"
INDEX_FILE="${WEB_ROOT}/index.html"
TERMS_FILE="${WEB_ROOT}/terms-of-use.txt"

# Validate required files
if [ ! -f "${TERMS_FILE}" ]; then
    echo "Error: Terms of use file not found: ${TERMS_FILE}"
    exit 1
fi

# Ensure web directory exists
mkdir -p "${WEB_ROOT}"

rm -f "${INDEX_FILE}" || echo "Index file does not exist"

# Generate the HTML header
cat <<EOF >"${INDEX_FILE}"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Browse: o!TR Public Datasets</title>
</head>
<body>
    <h1>Terms of Use</h1>
    <p>$(cat "${TERMS_FILE}")</p>

    <h1>Files in ${BUCKET_NAME}</h1>
    <ul>
EOF

# Append the list of file links to the HTML
echo "Listing files from gs://${BUCKET_NAME}/"
gcloud storage ls "gs://${BUCKET_NAME}/" | while read -r OBJECT; do
    FILE_URL="https://storage.googleapis.com/${OBJECT#gs://}"
    echo "        <li><a href=\"${FILE_URL}\" download>${OBJECT#gs://}</a></li>" >>"${INDEX_FILE}"
done

# Generate the HTML footer
cat <<EOF >>"${INDEX_FILE}"
    </ul>
</body>
</html>
EOF

echo "Index file generated at ${INDEX_FILE}"
