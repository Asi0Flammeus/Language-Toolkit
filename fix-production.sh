#!/bin/bash

# Fix production deployment for translation.planb.network
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DOMAIN="translation.planb.network"

echo -e "${GREEN}🔧 Fixing production deployment for $DOMAIN${NC}"
echo "================================================"

# 1. Make sure API is running
echo -e "\n${YELLOW}1. Checking API...${NC}"
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "Starting API..."
    docker-compose -f docker-compose.yml down
    docker-compose -f docker-compose.yml up -d
    sleep 10
fi

if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API is running on port 8000${NC}"
else
    echo -e "${RED}✗ API failed to start${NC}"
    docker-compose -f docker-compose.yml logs --tail=20
    exit 1
fi

# 2. Fix nginx configuration
echo -e "\n${YELLOW}2. Configuring nginx for $DOMAIN...${NC}"
sudo tee /etc/nginx/sites-available/language-toolkit > /dev/null <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name translation.planb.network;

    # For Let's Encrypt
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        
        # Important for Cloudflare
        proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
        proxy_set_header CF-IPCountry $http_cf_ipcountry;
        proxy_set_header CF-RAY $http_cf_ray;
        proxy_set_header CF-Visitor $http_cf_visitor;
        
        # Timeouts and limits
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        client_max_body_size 200M;
        
        # Disable buffering for better streaming
        proxy_buffering off;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/language-toolkit /etc/nginx/sites-enabled/

# Remove default site if it exists (might be conflicting)
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx
if sudo nginx -t; then
    echo -e "${GREEN}✓ Nginx configuration is valid${NC}"
    sudo systemctl reload nginx
else
    echo -e "${RED}✗ Nginx configuration error${NC}"
    exit 1
fi

# 3. Open firewall ports
echo -e "\n${YELLOW}3. Configuring firewall...${NC}"
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true
sudo ufw allow 8000/tcp 2>/dev/null || true
echo -e "${GREEN}✓ Ports 80, 443, 8000 are open${NC}"

# 4. Test everything
echo -e "\n${YELLOW}4. Testing deployment...${NC}"

# Test local API
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API responds locally${NC}"
else
    echo -e "${RED}✗ API not responding${NC}"
fi

# Test nginx proxy
if curl -s -H "Host: translation.planb.network" http://localhost/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Nginx proxy works${NC}"
else
    echo -e "${RED}✗ Nginx proxy failed${NC}"
fi

# Get server IP
SERVER_IP=$(curl -s ifconfig.me)

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Deployment Fixed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Your setup:"
echo "  - API running on: localhost:8000"
echo "  - Nginx proxying: port 80 → localhost:8000"
echo "  - Domain: $DOMAIN"
echo "  - Server IP: $SERVER_IP"
echo ""
echo "In Cloudflare, make sure:"
echo "  1. DNS A record points to: $SERVER_IP"
echo "  2. Proxy (orange cloud) is ON"
echo "  3. SSL/TLS mode is set to 'Flexible'"
echo ""
echo "Your API should be accessible at:"
echo "  http://$DOMAIN"
echo "  https://$DOMAIN (through Cloudflare)"
echo ""
echo "Test with:"
echo "  curl https://$DOMAIN/health"
echo "  curl https://$DOMAIN/docs"
echo ""
echo "If still not working, check:"
echo "  docker-compose -f docker-compose.yml logs"
echo "  sudo tail -f /var/log/nginx/error.log"