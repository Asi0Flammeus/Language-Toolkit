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

# Detect if running on Cloudron
IS_CLOUDRON=false
if [ -d "/etc/nginx/applications" ] && [ -d "/home/yellowtent" ]; then
    IS_CLOUDRON=true
    echo -e "${YELLOW}📦 Cloudron server detected${NC}"
else
    echo -e "${YELLOW}🖥️  Standard server detected${NC}"
fi

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

# Set paths based on server type
if [ "$IS_CLOUDRON" = true ]; then
    NGINX_CONF_PATH="/etc/nginx/applications/language-toolkit-testnet.conf"
    ACME_PATH="/home/yellowtent/platformdata/acme/"
    echo -e "${YELLOW}Using Cloudron nginx configuration${NC}"

    # Safety check: Look for existing conflicting configs
    echo -e "${YELLOW}Checking for existing nginx configs with this domain...${NC}"
    CONFLICTS=$(grep -l "server_name.*$DOMAIN" /etc/nginx/applications/*.conf 2>/dev/null | grep -v "language-toolkit-testnet.conf" || true)

    if [ -n "$CONFLICTS" ]; then
        echo -e "${RED}⚠️  WARNING: Found existing nginx configs for $DOMAIN:${NC}"
        echo "$CONFLICTS"
        echo ""
        echo -e "${YELLOW}This can cause conflicts. Do you want to remove the domain from these files? (y/n)${NC}"
        read -r remove_conflicts

        if [[ $remove_conflicts =~ ^[Yy]$ ]]; then
            for conf_file in $CONFLICTS; do
                echo -e "${YELLOW}Backing up $conf_file...${NC}"
                sudo cp "$conf_file" "$conf_file.backup.$(date +%s)"

                echo -e "${YELLOW}Removing server blocks with $DOMAIN from $conf_file...${NC}"
                # Remove server blocks containing this domain
                sudo awk -v domain="$DOMAIN" '
                    /^server \{/ { in_server=1; block="" }
                    in_server {
                        block = block $0 "\n"
                        if (/^\}/) {
                            if (block !~ "server_name.*" domain) {
                                printf "%s", block
                            }
                            in_server=0
                            block=""
                        }
                        next
                    }
                    !in_server { print }
                ' "$conf_file" > /tmp/nginx_cleaned.conf
                sudo mv /tmp/nginx_cleaned.conf "$conf_file"
            done
            echo -e "${GREEN}✓ Conflicts removed${NC}"
        else
            echo -e "${YELLOW}⚠️  Proceeding anyway. This may cause nginx conflicts.${NC}"
        fi
    else
        echo -e "${GREEN}✓ No conflicting configs found${NC}"
    fi
else
    NGINX_CONF_PATH="/etc/nginx/sites-available/language-toolkit-testnet"
    ACME_PATH="/var/www/html"
    echo -e "${YELLOW}Using standard nginx configuration${NC}"
fi

# Create nginx configuration
sudo tee $NGINX_CONF_PATH > /dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    # For Let's Encrypt verification
    location /.well-known/acme-challenge/ {
EOF

# Add the appropriate ACME challenge location
if [ "$IS_CLOUDRON" = true ]; then
    sudo tee -a $NGINX_CONF_PATH > /dev/null <<EOF
        default_type text/plain;
        alias $ACME_PATH;
EOF
else
    sudo tee -a $NGINX_CONF_PATH > /dev/null <<EOF
        root $ACME_PATH;
EOF
fi

# Continue with the rest of the configuration
sudo tee -a $NGINX_CONF_PATH > /dev/null <<EOF
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

# Enable the site (only for non-Cloudron)
if [ "$IS_CLOUDRON" = false ]; then
    sudo ln -sf /etc/nginx/sites-available/language-toolkit-testnet /etc/nginx/sites-enabled/
fi

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

    if [ "$IS_CLOUDRON" = true ]; then
        # For Cloudron, use webroot method
        echo -e "${YELLOW}Using webroot authentication for Cloudron...${NC}"
        sudo certbot certonly --webroot -w /home/yellowtent/platformdata/acme -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN

        if [ $? -eq 0 ]; then
            # Add HTTPS server block to the config
            sudo tee -a $NGINX_CONF_PATH > /dev/null <<EOF

# HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

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
            sudo systemctl reload nginx
            echo -e "${GREEN}✓ SSL certificate installed for testnet${NC}"
        else
            echo -e "${RED}✗ Failed to obtain SSL certificate${NC}"
        fi
    else
        # For standard servers, use nginx plugin
        sudo certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN --redirect
        echo -e "${GREEN}✓ SSL certificate installed for testnet${NC}"
    fi
else
    if [ "$IS_CLOUDRON" = true ]; then
        echo -e "${YELLOW}Skipping SSL setup. You can run later:${NC}"
        echo -e "  sudo certbot certonly --webroot -w /home/yellowtent/platformdata/acme -d $DOMAIN"
    else
        echo -e "${YELLOW}Skipping SSL setup. You can run later: sudo certbot --nginx -d $DOMAIN${NC}"
    fi
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
