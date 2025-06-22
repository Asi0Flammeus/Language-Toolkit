#!/bin/bash

# Language Toolkit API Deployment Script
# This script sets up the production environment for the Language Toolkit API

set -e

echo "🚀 Language Toolkit API Deployment Script"
echo "=========================================="

# Configuration
DOMAIN=${1:-"your-domain.com"}
EMAIL=${2:-"admin@your-domain.com"}

if [ "$DOMAIN" = "your-domain.com" ] || [ "$EMAIL" = "admin@your-domain.com" ]; then
    echo "❌ Please provide your domain and email:"
    echo "Usage: ./deploy.sh your-domain.com admin@your-domain.com"
    exit 1
fi

echo "📋 Domain: $DOMAIN"
echo "📧 Email: $EMAIL"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs temp ssl

# Update domain in nginx.conf
echo "🔧 Configuring nginx for domain: $DOMAIN"
sed -i "s/your-domain.com/$DOMAIN/g" nginx.conf

# Check if SSL certificates exist
if [ ! -f "ssl/cert.pem" ] || [ ! -f "ssl/key.pem" ]; then
    echo "🔐 SSL certificates not found. Setting up Let's Encrypt..."
    
    # Install certbot if not present
    if ! command -v certbot &> /dev/null; then
        echo "📦 Installing certbot..."
        sudo apt-get update
        sudo apt-get install -y certbot
    fi
    
    # Stop any existing nginx
    sudo systemctl stop nginx 2>/dev/null || true
    
    # Get SSL certificate
    echo "🔒 Obtaining SSL certificate for $DOMAIN..."
    sudo certbot certonly --standalone -d $DOMAIN --email $EMAIL --agree-tos --non-interactive
    
    # Copy certificates
    sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ssl/cert.pem
    sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ssl/key.pem
    sudo chown $USER:$USER ssl/*.pem
    
    echo "✅ SSL certificates configured"
else
    echo "✅ SSL certificates found"
fi

# Check if configuration files exist
if [ ! -f "api_keys.json" ]; then
    echo "⚠️  api_keys.json not found. Creating template..."
    cat > api_keys.json << EOF
{
  "deepl": "your-deepl-api-key",
  "openai": "your-openai-api-key",
  "elevenlabs": "your-elevenlabs-api-key",
  "convertapi": "your-convertapi-key"
}
EOF
    echo "📝 Please edit api_keys.json with your actual API keys"
fi

if [ ! -f "auth_tokens.json" ]; then
    echo "⚠️  auth_tokens.json not found. Copying from example..."
    cp auth_tokens.json.example auth_tokens.json
    echo "📝 Please edit auth_tokens.json with your desired authentication tokens"
fi

# Build and start services
echo "🏗️  Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check if services are running
if docker-compose ps | grep -q "Up"; then
    echo "✅ Services started successfully!"
    echo ""
    echo "🌐 Your API is now available at:"
    echo "   - HTTPS: https://$DOMAIN"
    echo "   - HTTP: http://$DOMAIN (redirects to HTTPS)"
    echo ""
    echo "📚 API Documentation:"
    echo "   - Swagger UI: https://$DOMAIN/docs"
    echo "   - ReDoc: https://$DOMAIN/redoc"
    echo ""
    echo "🔍 Health Check:"
    echo "   curl https://$DOMAIN/health"
    echo ""
    echo "📊 Monitor logs:"
    echo "   docker-compose logs -f"
    echo ""
    echo "🛠️  Manage services:"
    echo "   docker-compose stop    # Stop services"
    echo "   docker-compose start   # Start services"
    echo "   docker-compose restart # Restart services"
    echo "   docker-compose down    # Stop and remove containers"
else
    echo "❌ Failed to start services. Check logs:"
    docker-compose logs
    exit 1
fi

# Setup automatic certificate renewal
echo "🔄 Setting up automatic SSL certificate renewal..."
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && docker-compose restart nginx") | crontab -

echo ""
echo "🎉 Deployment completed successfully!"
echo "⚠️  Remember to:"
echo "   1. Edit api_keys.json with your actual API keys"
echo "   2. Edit auth_tokens.json with secure authentication tokens"
echo "   3. Configure your domain's DNS to point to this server"
echo "   4. Open ports 80 and 443 in your firewall"