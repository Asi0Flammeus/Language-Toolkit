#!/bin/bash

# Quick fix and deploy script
set -e

echo "🔧 Fixing and deploying Language Toolkit..."

# 1. Fix permissions
echo "Fixing permissions..."
mkdir -p logs temp uploads
sudo chmod -R 777 logs temp uploads

# 2. Rebuild with fixed Dockerfile
echo "Rebuilding Docker image..."
docker-compose down
docker-compose build --no-cache

# 3. Start the API
echo "Starting API..."
docker-compose up -d

# 4. Wait and test
echo "Waiting for API to start..."
sleep 10

# 5. Check status
echo ""
echo "📊 Status Check:"
echo "==============="

# Check if container is running
if docker ps | grep -q language-toolkit; then
    echo "✅ Container is running"
else
    echo "❌ Container is not running"
    docker-compose logs --tail=20
    exit 1
fi

# Check if API responds
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API is responding on port 8000"
    echo ""
    echo "🎉 Success! Your API is running at:"
    echo "   http://localhost:8000"
    echo "   http://$(hostname -I | awk '{print $1}'):8000"
else
    echo "❌ API is not responding"
    echo ""
    echo "Checking logs..."
    docker-compose logs --tail=20
fi

echo ""
echo "📝 Next steps:"
echo "1. Make sure port 8000 is open: sudo ufw allow 8000"
echo "2. For domain setup, run: ./deploy-production.sh your-domain.com"
echo "3. View logs: docker-compose logs -f"