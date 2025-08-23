#!/bin/bash

echo "🔧 Quick Fix for Permission Issues"
echo "================================="

# Stop everything
echo "Stopping containers..."
docker-compose down
docker stop language-toolkit 2>/dev/null || true
docker rm language-toolkit 2>/dev/null || true

# Fix permissions on host
echo "Fixing permissions..."
sudo rm -rf logs temp uploads 2>/dev/null || true
mkdir -p logs temp uploads
sudo chmod 777 logs temp uploads

# Clean Docker
echo "Cleaning Docker..."
docker system prune -f

# Rebuild with simple Dockerfile
echo "Building with simple Dockerfile..."
docker-compose build --no-cache

# Start
echo "Starting container..."
docker-compose up -d

# Wait a bit
sleep 5

# Check status
echo ""
echo "Checking status..."
docker ps | grep language-toolkit

# Test API
echo ""
echo "Testing API..."
curl -f http://localhost:8000/health && echo "✅ API is working!" || echo "❌ API not responding yet"

# Show logs
echo ""
echo "Recent logs:"
docker-compose logs --tail=10

echo ""
echo "✅ Done! Your API should be accessible at:"
echo "   http://localhost:8000"
echo "   http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "If still having issues, run: docker-compose logs -f"