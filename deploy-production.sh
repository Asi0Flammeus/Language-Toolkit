#!/bin/bash

# Language Toolkit - Production Deployment Script
# This script deploys the application to a production server with SSL support

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN=${1:-""}
EMAIL=${2:-""}
SSL_MODE=${3:-"letsencrypt"}  # letsencrypt, self-signed, or existing

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Language Toolkit - Production Deployment${NC}"
echo -e "${BLUE}========================================${NC}"

# Validate arguments
validate_args() {
    if [ -z "$DOMAIN" ]; then
        echo -e "${RED}Error: Domain name required${NC}"
        echo "Usage: $0 <domain> <email> [ssl-mode]"
        echo "  domain: Your domain name (e.g., api.example.com)"
        echo "  email: Admin email for SSL certificates"
        echo "  ssl-mode: letsencrypt (default), self-signed, or existing"
        exit 1
    fi
    
    if [ -z "$EMAIL" ]; then
        EMAIL="admin@$DOMAIN"
        echo -e "${YELLOW}Using default email: $EMAIL${NC}"
    fi
    
    echo -e "${GREEN}Configuration:${NC}"
    echo "  Domain: $DOMAIN"
    echo "  Email: $EMAIL"
    echo "  SSL Mode: $SSL_MODE"
}

# Check system requirements
check_requirements() {
    echo -e "\n${YELLOW}Checking requirements...${NC}"
    local missing=()
    
    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing+=("docker-compose")
    fi
    
    if [ "$SSL_MODE" == "letsencrypt" ] && ! command -v certbot &> /dev/null; then
        echo -e "${YELLOW}Installing certbot...${NC}"
        sudo apt-get update
        sudo apt-get install -y certbot
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${RED}Error: Missing required tools: ${missing[*]}${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ All requirements met${NC}"
}

# Setup production environment
setup_environment() {
    echo -e "\n${YELLOW}Setting up production environment...${NC}"
    
    # Check for production .env
    if [ ! -f .env.production ]; then
        if [ -f .env.example ]; then
            echo "Creating .env.production from .env.example..."
            cp .env.example .env.production
            
            # Update domain and email in .env.production
            sed -i "s/DOMAIN=.*/DOMAIN=$DOMAIN/" .env.production
            sed -i "s/EMAIL=.*/EMAIL=$EMAIL/" .env.production
            sed -i "s/SSL_ENABLED=.*/SSL_ENABLED=true/" .env.production
            sed -i "s/DEBUG_MODE=.*/DEBUG_MODE=false/" .env.production
            
            echo -e "${YELLOW}⚠ Please edit .env.production and add your API keys${NC}"
            echo "Press Enter to continue after editing..."
            read
        else
            echo -e "${RED}Error: .env.example not found${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✓ .env.production exists${NC}"
        # Update domain in case it changed
        sed -i "s/DOMAIN=.*/DOMAIN=$DOMAIN/" .env.production
    fi
    
    # Create necessary directories
    mkdir -p logs/api logs/nginx temp uploads nginx/ssl nginx/html
    echo -e "${GREEN}✓ Directories created${NC}"
    
    # Update nginx configuration with actual domain
    if [ -f nginx/nginx.production.conf ]; then
        sed -i "s/\${DOMAIN}/$DOMAIN/g" nginx/nginx.production.conf
        echo -e "${GREEN}✓ Nginx configuration updated${NC}"
    fi
}

# Setup SSL certificates
setup_ssl() {
    echo -e "\n${YELLOW}Setting up SSL certificates...${NC}"
    
    case "$SSL_MODE" in
        letsencrypt)
            setup_letsencrypt
            ;;
        self-signed)
            setup_self_signed
            ;;
        existing)
            echo -e "${YELLOW}Using existing SSL certificates${NC}"
            check_existing_ssl
            ;;
        *)
            echo -e "${RED}Invalid SSL mode: $SSL_MODE${NC}"
            exit 1
            ;;
    esac
}

# Setup Let's Encrypt SSL
setup_letsencrypt() {
    echo "Setting up Let's Encrypt SSL certificates..."
    
    # Start nginx temporarily for ACME challenge
    docker-compose -f docker-compose.production.yml up -d nginx
    
    # Wait for nginx to start
    sleep 5
    
    # Get certificate
    sudo certbot certonly \
        --webroot \
        --webroot-path=./nginx/html \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        --domains "$DOMAIN"
    
    # Copy certificates to project directory
    sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/fullchain.pem
    sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/privkey.pem
    sudo cp /etc/letsencrypt/live/$DOMAIN/chain.pem nginx/ssl/chain.pem
    sudo chown $USER:$USER nginx/ssl/*.pem
    
    echo -e "${GREEN}✓ Let's Encrypt SSL certificates obtained${NC}"
    
    # Setup auto-renewal
    setup_ssl_renewal
}

# Setup self-signed SSL
setup_self_signed() {
    echo "Creating self-signed SSL certificates..."
    
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout nginx/ssl/privkey.pem \
        -out nginx/ssl/fullchain.pem \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"
    
    cp nginx/ssl/fullchain.pem nginx/ssl/chain.pem
    
    echo -e "${GREEN}✓ Self-signed SSL certificates created${NC}"
    echo -e "${YELLOW}⚠ Warning: Self-signed certificates will show security warnings${NC}"
}

# Check existing SSL certificates
check_existing_ssl() {
    if [ ! -f nginx/ssl/fullchain.pem ] || [ ! -f nginx/ssl/privkey.pem ]; then
        echo -e "${RED}Error: SSL certificates not found in nginx/ssl/${NC}"
        echo "Please place your certificates:"
        echo "  - nginx/ssl/fullchain.pem"
        echo "  - nginx/ssl/privkey.pem"
        echo "  - nginx/ssl/chain.pem (optional)"
        exit 1
    fi
    echo -e "${GREEN}✓ Existing SSL certificates found${NC}"
}

# Setup SSL auto-renewal
setup_ssl_renewal() {
    echo "Setting up SSL auto-renewal..."
    
    # Create renewal script
    cat > renew-ssl.sh << 'EOF'
#!/bin/bash
certbot renew --quiet
if [ $? -eq 0 ]; then
    cp /etc/letsencrypt/live/DOMAIN/fullchain.pem /path/to/project/nginx/ssl/fullchain.pem
    cp /etc/letsencrypt/live/DOMAIN/privkey.pem /path/to/project/nginx/ssl/privkey.pem
    cp /etc/letsencrypt/live/DOMAIN/chain.pem /path/to/project/nginx/ssl/chain.pem
    docker-compose -f docker-compose.production.yml restart nginx
fi
EOF
    
    # Update script with actual values
    sed -i "s|DOMAIN|$DOMAIN|g" renew-ssl.sh
    sed -i "s|/path/to/project|$(pwd)|g" renew-ssl.sh
    chmod +x renew-ssl.sh
    
    # Add to crontab
    (crontab -l 2>/dev/null; echo "0 2 * * * $(pwd)/renew-ssl.sh") | crontab -
    
    echo -e "${GREEN}✓ SSL auto-renewal configured${NC}"
}

# Build and deploy
deploy() {
    echo -e "\n${YELLOW}Building and deploying application...${NC}"
    
    # Build image
    docker-compose -f docker-compose.production.yml build --no-cache
    
    # Stop existing containers
    docker-compose -f docker-compose.production.yml down 2>/dev/null || true
    
    # Start all services
    docker-compose -f docker-compose.production.yml up -d
    
    # Wait for services to be ready
    echo -n "Waiting for services to start"
    for i in {1..60}; do
        if curl -k -s https://$DOMAIN/health > /dev/null 2>&1; then
            echo -e "\n${GREEN}✓ Services are running${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    if ! curl -k -s https://$DOMAIN/health > /dev/null 2>&1; then
        echo -e "\n${RED}Warning: Health check failed${NC}"
        echo "Check logs with: docker-compose -f docker-compose.production.yml logs"
    fi
}

# Setup firewall
setup_firewall() {
    echo -e "\n${YELLOW}Configuring firewall...${NC}"
    
    if command -v ufw &> /dev/null; then
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        sudo ufw allow 22/tcp
        echo -e "${GREEN}✓ Firewall configured${NC}"
    else
        echo -e "${YELLOW}UFW not found, please configure firewall manually${NC}"
    fi
}

# Setup monitoring
setup_monitoring() {
    echo -e "\n${YELLOW}Setting up monitoring...${NC}"
    
    # Create monitoring directory
    mkdir -p monitoring
    
    # Create basic Prometheus configuration
    cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'language-toolkit-api'
    static_configs:
      - targets: ['api:8000']
EOF
    
    echo -e "${GREEN}✓ Basic monitoring configured${NC}"
    echo -e "${YELLOW}To enable monitoring, run: docker-compose -f docker-compose.production.yml --profile monitoring up -d${NC}"
}

# Display deployment status
display_status() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Production Deployment Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo "Service URLs:"
    echo "  - API: https://$DOMAIN"
    echo "  - Swagger UI: https://$DOMAIN/docs"
    echo "  - ReDoc: https://$DOMAIN/redoc"
    echo "  - Health: https://$DOMAIN/health"
    echo
    echo "Management commands:"
    echo "  - View logs: docker-compose -f docker-compose.production.yml logs -f"
    echo "  - Restart services: docker-compose -f docker-compose.production.yml restart"
    echo "  - Stop services: docker-compose -f docker-compose.production.yml down"
    echo "  - Update deployment: git pull && ./deploy-production.sh $DOMAIN $EMAIL"
    echo
    if [ "$SSL_MODE" == "letsencrypt" ]; then
        echo "SSL certificate will auto-renew via cron job"
    fi
    echo
    echo -e "${GREEN}Deployment successful! Your API is now live at https://$DOMAIN${NC}"
}

# Health check
perform_health_check() {
    echo -e "\n${YELLOW}Performing health check...${NC}"
    
    response=$(curl -k -s -o /dev/null -w "%{http_code}" https://$DOMAIN/health)
    
    if [ "$response" == "200" ]; then
        echo -e "${GREEN}✓ API is healthy and responding${NC}"
    else
        echo -e "${RED}✗ Health check failed (HTTP $response)${NC}"
        echo "Check logs for more information"
    fi
}

# Main execution
main() {
    validate_args
    check_requirements
    setup_environment
    setup_ssl
    setup_firewall
    deploy
    setup_monitoring
    perform_health_check
    display_status
}

# Handle script termination
trap 'echo -e "\n${YELLOW}Deployment interrupted${NC}"; exit 1' INT TERM

# Run main function
main "$@"