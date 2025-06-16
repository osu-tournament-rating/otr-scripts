#!/bin/bash

# Check if script is being sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Error: This script must be sourced, not executed."
    echo "Usage: source ./load-env.sh"
    exit 1
fi

# Auto-detect environment from hostname if ENV is not set
if [ -z "$ENV" ]; then
    HOSTNAME=$(hostname)
    if [[ "$HOSTNAME" == otr-staging ]]; then
        ENV="staging"
        echo "Auto-detected environment: staging (from hostname: $HOSTNAME)"
    elif [[ "$HOSTNAME" == otr-prod ]]; then
        ENV="production"
        echo "Auto-detected environment: production (from hostname: $HOSTNAME)"
    else
        echo "Error: Could not auto-detect environment from hostname: $HOSTNAME"
        echo "Please set ENV manually: ENV=staging or ENV=production"
        exit 1
    fi
fi

# Load shared properties
SHARED_ENV_FILE="env/shared.env"
if [ -f "$SHARED_ENV_FILE" ]; then
    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        # Remove leading/trailing whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        # Export the variable
        export "$key=$value"
    done <"$SHARED_ENV_FILE"
fi

ENV_FILE="env/${ENV}.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Environment file not found: $ENV_FILE"
    exit 1
fi

# Load environment-specific properties
while IFS='=' read -r key value; do
    # Skip empty lines and comments
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
    # Remove leading/trailing whitespace
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    # Export the variable
    export "$key=$value"

done <"$ENV_FILE"

# Load secrets if they exist
SECRETS_FILE="env/secrets.env"
if [ -f "$SECRETS_FILE" ]; then
    echo "Loading secrets from: $SECRETS_FILE"
    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        # Remove leading/trailing whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        # Export the variable
        export "$key=$value"
    done <"$SECRETS_FILE"
else
    echo "Warning: No secrets file found at $SECRETS_FILE"
    echo "If you need to use secrets, copy env/secrets.template.env to env/secrets.env and populate it with actual values."
fi

echo "Loaded environment: $ENVIRONMENT"
