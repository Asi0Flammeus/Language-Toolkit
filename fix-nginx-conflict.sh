#!/bin/bash

# Fix nginx conflict by removing the old languagetoolkit server block from default.conf

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Fixing nginx conflict...${NC}"

# Backup the default.conf
echo -e "${YELLOW}Creating backup...${NC}"
sudo cp /etc/nginx/applications/default.conf /etc/nginx/applications/default.conf.backup.$(date +%s)

# Remove the languagetoolkit server block from default.conf
# The server block starts at line 174 and we need to find where it ends
echo -e "${YELLOW}Removing conflicting server block from default.conf...${NC}"

# Use sed to delete from line 174 to the end of that server block
# We'll look for the pattern and delete the entire server block
sudo sed -i '/server {/,/^}/{
    /server_name languagetoolkit\.planbtest\.network/,/^}$/d
}' /etc/nginx/applications/default.conf 2>/dev/null || {
    echo -e "${YELLOW}Using alternative removal method...${NC}"
    # Alternative: use awk to remove the entire server block
    sudo awk '
    /server \{/ { block=1; buf=$0; next }
    block {
        buf = buf "\n" $0
        if (/^\}/) {
            if (buf !~ /server_name languagetoolkit\.planbtest\.network/) {
                print buf
            }
            block=0
            buf=""
            next
        }
    }
    !block { print }
    ' /etc/nginx/applications/default.conf > /tmp/default.conf.tmp

    sudo mv /tmp/default.conf.tmp /etc/nginx/applications/default.conf
}

# Test nginx configuration
echo -e "${YELLOW}Testing nginx configuration...${NC}"
sudo nginx -t

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Nginx config is valid${NC}"

    # Reload nginx
    echo -e "${YELLOW}Reloading nginx...${NC}"
    sudo systemctl reload nginx

    echo -e "${GREEN}✓ Nginx reloaded successfully${NC}"
    echo ""
    echo -e "${GREEN}Conflict resolved! Testing...${NC}"
    sleep 2

    # Test the endpoint
    echo -e "${YELLOW}Testing local endpoint...${NC}"
    curl -s http://localhost/health -H "Host: languagetoolkit.planbtest.network" | jq . 2>/dev/null || curl -s http://localhost/health -H "Host: languagetoolkit.planbtest.network"

    echo ""
    echo -e "${GREEN}=========================================="
    echo "✅ Fix complete!"
    echo -e "=========================================="
    echo ""
    echo "Now clear Cloudflare cache and test:"
    echo "  https://languagetoolkit.planbtest.network/health"
    echo ""
else
    echo -e "${RED}✗ Nginx config has errors${NC}"
    echo -e "${YELLOW}Restoring backup...${NC}"
    sudo cp /etc/nginx/applications/default.conf.backup.$(ls -t /etc/nginx/applications/default.conf.backup.* | head -1) /etc/nginx/applications/default.conf
    exit 1
fi
