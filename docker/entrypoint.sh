#!/bin/bash
set -e

echo "Starting Language Toolkit API..."

# Create necessary directories
mkdir -p /app/logs /app/temp /app/uploads

# Start the application
exec "$@"