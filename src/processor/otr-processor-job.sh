#!/bin/bash

# Source environment variables
# shellcheck source=/dev/null
source "${HOME}/otr-scripts/src/load-env.sh"

TAG=$ENVIRONMENT
# If the environment is equal to "production", use "latest" as the tag instead of ${ENVIRONMENT}
if [[ $ENVIRONMENT == "production" ]]; then
    TAG=latest
fi

echo "Running otr-processor:${TAG} via docker"

docker run --network host -e CONNECTION_STRING="postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@localhost:5432/${DATABASE_NAME}" -e "RABBITMQ_URL=${RABBITMQ_URL}" -e RUST_LOG=info --rm "stagecodes/otr-processor:${TAG}"
docker rmi "stagecodes/otr-processor:${ENVIRONMENT}"

echo 'Finished'