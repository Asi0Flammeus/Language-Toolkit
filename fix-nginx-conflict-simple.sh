#!/bin/bash

# Simple fix: Remove the conflicting languagetoolkit server block from default.conf

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Fixing nginx conflict for languagetoolkit.planbtest.network${NC}"
echo "=========================================="

# Backup the default.conf
BACKUP_FILE="/etc/nginx/applications/default.conf.backup.$(date +%s)"
echo -e "${YELLOW}Creating backup: $BACKUP_FILE${NC}"
sudo cp /etc/nginx/applications/default.conf "$BACKUP_FILE"

# Remove lines 174-303 (the conflicting server block)
echo -e "${YELLOW}Removing conflicting server block (lines 174-303)...${NC}"
sudo sed -i '174,303d' /etc/nginx/applications/default.conf

# Verify the removal
echo -e "${YELLOW}Verifying removal...${NC}"
if grep -q "server_name languagetoolkit.planbtest.network" /etc/nginx/applications/default.conf; then
    echo -e "${RED}✗ Failed to remove conflict${NC}"
    echo -e "${YELLOW}Restoring backup...${NC}"
    sudo cp "$BACKUP_FILE" /etc/nginx/applications/default.conf
    exit 1
fi

echo -e "${GREEN}✓ Conflicting server block removed${NC}"

# Test nginx configuration
echo -e "${YELLOW}Testing nginx configuration...${NC}"
if sudo nginx -t 2>&1 | grep -q "conflicting server name"; then
    echo -e "${RED}✗ Still have conflicts!${NC}"
    sudo nginx -t
    exit 1
fi

if sudo nginx -t; then
    echo -e "${GREEN}✓ Nginx config is valid - no more conflicts!${NC}"

    # Reload nginx
    echo -e "${YELLOW}Reloading nginx...${NC}"
    sudo systemctl reload nginx
    echo -e "${GREEN}✓ Nginx reloaded${NC}"

    # Wait for reload
    sleep 2

    # Test the endpoint
    echo ""
    echo -e "${YELLOW}Testing endpoint...${NC}"
    if curl -s http://localhost/health -H "Host: languagetoolkit.planbtest.network" | grep -q "status"; then
        echo -e "${GREEN}✓ Local test successful!${NC}"
        echo ""
        curl -s http://localhost/health -H "Host: languagetoolkit.planbtest.network" | head -5
    else
        echo -e "${YELLOW}⚠ Endpoint test failed${NC}"
    fi

    echo ""
    echo -e "${GREEN}=========================================="
    echo "✅ Conflict resolved!"
    echo -e "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Clear Cloudflare cache for languagetoolkit.planbtest.network"
    echo "2. Test: https://languagetoolkit.planbtest.network/health"
    echo ""
    echo "Backup saved at: $BACKUP_FILE"
else
    echo -e "${RED}✗ Nginx config has errors${NC}"
    echo -e "${YELLOW}Restoring backup...${NC}"
    sudo cp "$BACKUP_FILE" /etc/nginx/applications/default.conf
    exit 1
fi
