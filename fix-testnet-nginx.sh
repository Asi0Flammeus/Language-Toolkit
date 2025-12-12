#!/bin/bash

# Fix script for Cloudron nginx configuration
# This moves the nginx config to the correct location for Cloudron

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Fixing Cloudron nginx configuration for testnet...${NC}"

# Create the config in Cloudron's applications directory
echo -e "${YELLOW}Creating nginx config in Cloudron applications directory...${NC}"

sudo tee /etc/nginx/applications/language-toolkit-testnet.conf > /dev/null <<'EOF'
# Language Toolkit Testnet
server {
    listen 80;
    listen [::]:80;
    server_name languagetoolkit.planbtest.network;

    # For Let's Encrypt verification
    location /.well-known/acme-challenge/ {
        default_type text/plain;
        alias /home/yellowtent/platformdata/acme/;
    }

    location / {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # File uploads
        client_max_body_size 200M;
    }
}

# HTTPS server (will be configured after SSL cert is obtained)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name languagetoolkit.planbtest.network;

    # Temporary self-signed cert location (will be replaced by Let's Encrypt)
    ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;

    location / {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;

        # File uploads
        client_max_body_size 200M;
    }
}
EOF

echo -e "${GREEN}✓ Config created${NC}"

# Test nginx configuration
echo -e "${YELLOW}Testing nginx configuration...${NC}"
sudo nginx -t

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Nginx config is valid${NC}"

    # Reload nginx
    echo -e "${YELLOW}Reloading nginx...${NC}"
    sudo systemctl reload nginx

    echo -e "${GREEN}✓ Nginx reloaded${NC}"
else
    echo -e "${RED}✗ Nginx config has errors${NC}"
    exit 1
fi

# Wait a moment for nginx to reload
sleep 2

# Test the endpoint
echo -e "${YELLOW}Testing HTTP endpoint...${NC}"
if curl -s http://languagetoolkit.planbtest.network/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ HTTP endpoint is working!${NC}"
else
    echo -e "${YELLOW}⚠ HTTP endpoint not accessible yet (might be DNS/Cloudflare caching)${NC}"
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Next steps:"
echo -e "=========================================${NC}"
echo ""
echo "1. Test the HTTP endpoint:"
echo "   curl http://languagetoolkit.planbtest.network/health"
echo ""
echo "2. If Cloudflare is in front, you may need to:"
echo "   - Pause Cloudflare proxy (orange cloud → grey cloud)"
echo "   - Or configure Cloudflare SSL to 'Full' or 'Full (strict)'"
echo ""
echo "3. Set up SSL certificate:"
echo "   sudo certbot certonly --webroot -w /home/yellowtent/platformdata/acme -d languagetoolkit.planbtest.network"
echo ""
echo "4. After getting the cert, update the nginx config:"
echo "   ssl_certificate /etc/letsencrypt/live/languagetoolkit.planbtest.network/fullchain.pem;"
echo "   ssl_certificate_key /etc/letsencrypt/live/languagetoolkit.planbtest.network/privkey.pem;"
echo ""
echo "5. Reload nginx:"
echo "   sudo systemctl reload nginx"
echo ""
