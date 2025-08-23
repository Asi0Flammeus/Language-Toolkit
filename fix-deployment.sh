#!/bin/bash

echo "🔧 Fixing deployment issues..."

# Check what's using port 80
echo "Checking port 80..."
sudo lsof -i :80

# Stop any existing nginx
echo "Stopping system nginx if running..."
sudo systemctl stop nginx 2>/dev/null || true
sudo service nginx stop 2>/dev/null || true

# Stop any Docker containers using port 80
echo "Stopping Docker containers on port 80..."
docker ps --filter "publish=80" -q | xargs -r docker stop

# Stop our containers if running
echo "Stopping language-toolkit containers..."
docker-compose -f docker-compose.server.yml down

# Now start fresh
echo "Starting services..."
docker-compose -f docker-compose.server.yml up -d

echo "✅ Done! Checking status..."
docker-compose -f docker-compose.server.yml ps