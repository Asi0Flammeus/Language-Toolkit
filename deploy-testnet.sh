#!/bin/bash

# Simple Testnet Deployment Script
set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🧪 Language Toolkit - Testnet Deployment${NC}"
echo "=========================================="

# Get domain from argument or prompt
DOMAIN=${1:-""}
if [ -z "$DOMAIN" ]; then
    echo -e "${YELLOW}Enter your testnet domain (e.g., testnet.example.com):${NC}"
    read DOMAIN
fi

if [ -z "$DOMAIN" ] || [ "$DOMAIN" == "example.com" ]; then
    echo -e "${RED}Error: Valid domain required${NC}"
    exit 1
fi

echo -e "${GREEN}Deploying testnet for domain: $DOMAIN${NC}"

# Step 1: Setup environment
echo -e "\n${YELLOW}Step 1: Setting up testnet environment...${NC}"
if [ ! -f .env.testnet ]; then
    cp .env.example .env.testnet
    echo -e "${YELLOW}⚠️  Created .env.testnet file. Please add your TESTNET API keys!${NC}"
fi

echo -e "${GREEN}✓ Using testnet environment (.env.testnet)${NC}"

# Create testnet-specific directories
mkdir -p logs-testnet temp-testnet uploads-testnet ssl
chmod 777 logs-testnet temp-testnet uploads-testnet

# Step 2: Build and start API
echo -e "\n${YELLOW}Step 2: Building and starting testnet API...${NC}"
# Use testnet-specific docker-compose file (API on port 8001)
docker-compose -f docker-compose.testnet.yml down 2>/dev/null || true
docker-compose -f docker-compose.testnet.yml build --no-cache
docker-compose -f docker-compose.testnet.yml up -d

# Wait for API to start (on port 8001)
echo -n "Waiting for testnet API to start"
for i in {1..30}; do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Step 3: Setup system nginx (since port 80 is already in use)
echo -e "\n${YELLOW}Step 3: Configuring system nginx for testnet...${NC}"

# Create nginx configuration
sudo tee /etc/nginx/sites-available/language-toolkit-testnet > /dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    # For Let's Encrypt verification
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # File uploads
        client_max_body_size 200M;
    }
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/language-toolkit-testnet /etc/nginx/sites-enabled/
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

echo -e "${GREEN}✓ Nginx configured for testnet${NC}"

# Step 4: Setup SSL with Certbot
echo -e "\n${YELLOW}Step 4: Setting up SSL certificate for testnet...${NC}"
echo -e "${YELLOW}Do you want to setup SSL with Let's Encrypt? (y/n)${NC}"
read -r setup_ssl

if [[ $setup_ssl =~ ^[Yy]$ ]]; then
    # Install certbot if not installed
    if ! command -v certbot &> /dev/null; then
        sudo apt update
        sudo apt install -y certbot python3-certbot-nginx
    fi
    
    # Get certificate
    sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN --redirect
    
    echo -e "${GREEN}✓ SSL certificate installed for testnet${NC}"
else
    echo -e "${YELLOW}Skipping SSL setup. You can run later: sudo certbot --nginx -d $DOMAIN${NC}"
fi

# Step 5: Configure firewall
echo -e "\n${YELLOW}Step 5: Configuring firewall...${NC}"
sudo ufw allow 22/tcp 2>/dev/null || true
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true
sudo ufw allow 8001/tcp 2>/dev/null || true
echo -e "${GREEN}✓ Firewall configured${NC}"

# Step 6: Test the deployment
echo -e "\n${YELLOW}Step 6: Testing testnet deployment...${NC}"

# Test local API
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Testnet API is running on port 8001${NC}"
else
    echo -e "${RED}✗ Testnet API is not responding${NC}"
    echo "Check logs: docker-compose -f docker-compose.testnet.yml logs"
fi

# Test nginx proxy
if curl -s http://$DOMAIN/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Nginx proxy is working${NC}"
else
    echo -e "${YELLOW}⚠ Nginx proxy not accessible yet (DNS might be propagating)${NC}"
fi

# Display summary
echo -e "\n${GREEN}=========================================="
echo -e "🧪 Testnet Deployment Complete!"
echo -e "=========================================="
echo -e "${NC}"
echo "Your TESTNET API is accessible at:"
if [[ $setup_ssl =~ ^[Yy]$ ]]; then
    echo "  🔒 https://$DOMAIN"
else
    echo "  🔓 http://$DOMAIN"
fi
echo "  📚 API Docs: http://$DOMAIN/docs"
echo ""
echo "⚠️  TESTNET ENVIRONMENT - Not for production use!"
echo "  Running on port 8001 (production uses 8000)"
echo ""
echo "Useful commands:"
echo "  docker-compose -f docker-compose.testnet.yml logs -f    # View logs"
echo "  docker-compose -f docker-compose.testnet.yml restart    # Restart API"
echo "  sudo nginx -t                 # Test nginx config"
echo "  sudo systemctl status nginx   # Check nginx status"
echo ""
echo "If DNS is not pointing to this server yet:"
echo "  1. Add an A record pointing $DOMAIN to $(curl -s ifconfig.me)"
echo "  2. Wait for DNS propagation (5-30 minutes)"
echo ""

# Check if API keys are configured
if grep -q "OPENAI_API_KEY=$" .env.testnet 2>/dev/null || grep -q "OPENAI_API_KEY=\"\"" .env.testnet 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Don't forget to add your TESTNET API keys to .env.testnet file!${NC}"
fi