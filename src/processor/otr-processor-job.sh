#!/bin/bash

# Source environment variables
# shellcheck source=/dev/null
source "${HOME}/otr-scripts/src/load-env.sh"

echo 'Running otr-processor:Staging via docker'

docker run --network host -e CONNECTION_STRING="postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@localhost:5432/${DATABASE_NAME}" -e "RABBITMQ_URL=${RABBITMQ_URL}" -e RUST_LOG=info --rm "stagecodes/otr-processor:${ENVIRONMENT}"
docker rmi "stagecodes/otr-processor:${ENVIRONMENT}"

echo 'Finished'