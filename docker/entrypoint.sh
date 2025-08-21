#!/bin/bash
set -e

echo "Starting Language Toolkit API..."

# Create necessary directories
mkdir -p /app/logs /app/temp /app/uploads

# Ensure log files exist
touch /app/logs/access.log /app/logs/error.log

# Check for required configuration files
if [ ! -f "/app/client_credentials.json" ]; then
    echo "WARNING: /app/client_credentials.json not found. Using example file..."
    if [ -f "/app/client_credentials.json.example" ]; then
        cp /app/client_credentials.json.example /app/client_credentials.json
        echo "INFO: Created client_credentials.json from example"
    else
        echo "ERROR: Neither client_credentials.json nor client_credentials.json.example found!"
        exit 1
    fi
fi

if [ ! -f "/app/api_keys.json" ]; then
    echo "WARNING: /app/api_keys.json not found. Using example file..."
    if [ -f "/app/api_keys.json.example" ]; then
        cp /app/api_keys.json.example /app/api_keys.json
        echo "INFO: Created api_keys.json from example"
    else
        echo "ERROR: Neither api_keys.json nor api_keys.json.example found!"
        exit 1
    fi
fi

if [ ! -f "/app/auth_tokens.json" ]; then
    echo "WARNING: /app/auth_tokens.json not found. Using example file..."
    if [ -f "/app/auth_tokens.json.example" ]; then
        cp /app/auth_tokens.json.example /app/auth_tokens.json
        echo "INFO: Created auth_tokens.json from example"
    else
        echo "ERROR: Neither auth_tokens.json nor auth_tokens.json.example found!"
        exit 1
    fi
fi

# Wait for potential dependencies
echo "Waiting 5 seconds for dependencies..."
sleep 5

# Start the application
echo "Starting application with command: $@"
exec "$@"