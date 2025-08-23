#!/bin/bash

echo "🔧 Fixing deployment issues..."

# Fix permissions
echo "Fixing permissions..."
sudo chown -R 1000:1000 logs/ temp/ uploads/ 2>/dev/null || true
sudo chmod -R 755 logs/ temp/ uploads/ 2>/dev/null || true

# Create directories if they don't exist
mkdir -p logs temp uploads ssl
sudo chmod 755 logs temp uploads

# Stop and clean up
echo "Cleaning up old containers..."
docker-compose down
docker-compose -f docker-compose.server.yml down

# Remove old volumes that might have wrong permissions
docker volume prune -f

# Start fresh with the simple setup (no nginx container)
echo "Starting API directly..."
docker-compose up -d

# Wait for API to be ready
echo "Waiting for API to start..."
sleep 10

# Check if it's running
echo "Checking API status..."
curl -f http://localhost:8000/health || echo "API not responding yet"

# Show logs
echo ""
echo "📋 API Logs:"
docker-compose logs --tail=20

echo ""
echo "✅ Fix applied!"
echo ""
echo "Your API should now be accessible at:"
echo "  - Direct: http://your-server-ip:8000"
echo "  - Through Cloudflare: Configure Cloudflare to point to port 8000"
echo ""
echo "To configure Cloudflare:"
echo "1. Go to Cloudflare Dashboard"
echo "2. Set SSL/TLS to 'Flexible' mode"
echo "3. Make sure your DNS A record points to your server IP"
echo "4. In Cloudflare, you may need to add a Page Rule to bypass cache for API"