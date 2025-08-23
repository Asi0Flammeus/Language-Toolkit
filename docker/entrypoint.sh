#!/bin/bash
set -e

echo "Starting Language Toolkit API..."

# Ensure directories exist and are writable
mkdir -p /app/logs /app/temp /app/uploads || true
chmod 777 /app/logs /app/temp /app/uploads || true

# Start the application
exec "$@"