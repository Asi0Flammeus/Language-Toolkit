#!/bin/bash

# Language Toolkit - Local Development Deployment Script
# This script sets up and runs the application locally for development/testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Language Toolkit - Local Development Setup${NC}"
echo -e "${GREEN}========================================${NC}"

# Check for required tools
check_requirements() {
    local missing=()
    
    if ! command -v docker &> /dev/null; then
        missing+=("docker")
    fi
    
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        missing+=("docker-compose")
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        echo -e "${RED}Error: Missing required tools: ${missing[*]}${NC}"
        echo "Please install the missing tools and try again."
        exit 1
    fi
    
    echo -e "${GREEN}✓ All requirements met${NC}"
}

# Setup environment
setup_environment() {
    echo -e "\n${YELLOW}Setting up environment...${NC}"
    
    # Check if .env exists
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            echo "Creating .env from .env.example..."
            cp .env.example .env
            echo -e "${YELLOW}⚠ Please edit .env and add your API keys${NC}"
            echo "Press Enter to continue after editing .env..."
            read
        else
            echo -e "${RED}Error: .env.example not found${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✓ .env file exists${NC}"
    fi
    
    # Create necessary directories
    mkdir -p logs temp uploads nginx/ssl
    echo -e "${GREEN}✓ Directories created${NC}"
}

# Build Docker image
build_image() {
    echo -e "\n${YELLOW}Building Docker image...${NC}"
    docker-compose build --no-cache
    echo -e "${GREEN}✓ Docker image built${NC}"
}

# Start services
start_services() {
    echo -e "\n${YELLOW}Starting services...${NC}"
    
    # Stop any existing containers
    docker-compose down 2>/dev/null || true
    
    # Start services
    docker-compose up -d
    
    # Wait for services to be ready
    echo -n "Waiting for API to be ready"
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo -e "\n${GREEN}✓ Services are ready${NC}"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "\n${RED}Error: API failed to start${NC}"
        echo "Check logs with: docker-compose logs api"
        exit 1
    fi
}

# Display status
display_status() {
    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Local Development Environment Ready!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo
    echo "Service URLs:"
    echo "  - API: http://localhost:8000"
    echo "  - Swagger UI: http://localhost:8000/docs"
    echo "  - ReDoc: http://localhost:8000/redoc"
    echo "  - Health Check: http://localhost:8000/health"
    echo
    echo "Useful commands:"
    echo "  - View logs: docker-compose logs -f"
    echo "  - Stop services: docker-compose down"
    echo "  - Restart services: docker-compose restart"
    echo "  - Rebuild image: docker-compose build --no-cache"
    echo
    echo -e "${GREEN}API is running and ready for development!${NC}"
}

# Main execution
main() {
    check_requirements
    setup_environment
    
    # Ask if user wants to rebuild
    echo -e "\n${YELLOW}Do you want to rebuild the Docker image? (y/N)${NC}"
    read -r rebuild
    if [[ $rebuild =~ ^[Yy]$ ]]; then
        build_image
    fi
    
    start_services
    display_status
    
    # Ask if user wants to follow logs
    echo -e "\n${YELLOW}Do you want to follow the logs? (y/N)${NC}"
    read -r follow_logs
    if [[ $follow_logs =~ ^[Yy]$ ]]; then
        docker-compose logs -f
    fi
}

# Handle script termination
trap 'echo -e "\n${YELLOW}Deployment interrupted${NC}"; exit 1' INT TERM

# Run main function
main "$@"