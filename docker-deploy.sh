#!/bin/bash

# Enhanced Docker Deployment Script for Language Toolkit API
# Handles configuration setup, health checks, and proper deployment

set -e

echo "🚀 Language Toolkit API Docker Deployment"
echo "=========================================="

# Function to check if file exists and copy from example if needed
setup_config_file() {
    local filename=$1
    local example_file="${filename}.example"
    
    if [ ! -f "$filename" ]; then
        if [ -f "$example_file" ]; then
            echo "📋 Creating $filename from example..."
            cp "$example_file" "$filename"
            echo "⚠️  IMPORTANT: Please edit $filename with your actual values!"
        else
            echo "❌ ERROR: Neither $filename nor $example_file found!"
            exit 1
        fi
    else
        echo "✅ $filename already exists"
    fi
}

# Function to wait for container health
wait_for_health() {
    local container_name=$1
    local max_attempts=30
    local attempt=1
    
    echo "⏳ Waiting for $container_name to be healthy..."
    
    while [ $attempt -le $max_attempts ]; do
        if docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null | grep -q "healthy"; then
            echo "✅ $container_name is healthy!"
            return 0
        fi
        
        echo "Attempt $attempt/$max_attempts - waiting..."
        sleep 10
        ((attempt++))
    done
    
    echo "❌ $container_name failed to become healthy"
    echo "📋 Container logs:"
    docker logs "$container_name" --tail 20
    return 1
}

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Set up Docker Compose command (handle both docker-compose and docker compose)
COMPOSE_CMD="docker-compose"
if ! command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker compose"
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs temp uploads ssl

# Setup configuration files
echo "🔧 Setting up configuration files..."
setup_config_file "api_keys.json"
setup_config_file "auth_tokens.json"  
setup_config_file "client_credentials.json"

# Stop existing containers
echo "🛑 Stopping existing containers..."
$COMPOSE_CMD down --remove-orphans || true

# Build and start containers
echo "🏗️  Building and starting containers..."
$COMPOSE_CMD build --no-cache
$COMPOSE_CMD up -d

# Wait for API container to be healthy
echo "🏥 Checking container health..."
if wait_for_health "language-toolkit-api"; then
    echo ""
    echo "🎉 Deployment successful!"
    echo ""
    echo "📡 API Endpoints:"
    echo "   Health check: http://localhost:8000/health"
    echo "   API docs: http://localhost:8000/docs"
    echo ""
    echo "🌐 Nginx Proxy:"
    echo "   HTTP: http://localhost:8080"
    echo "   HTTPS: https://localhost:8443"
    echo ""
    echo "📊 Monitor with:"
    echo "   docker-compose logs -f api"
    echo "   docker-compose ps"
    echo ""
    
    # Test health endpoint
    echo "🧪 Testing health endpoint..."
    sleep 5
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Health endpoint is responding"
    else
        echo "⚠️  Health endpoint test failed - container may still be starting"
    fi
    
else
    echo ""
    echo "❌ Deployment failed!"
    echo ""
    echo "📋 Troubleshooting:"
    echo "   1. Check container logs: docker logs language-toolkit-api"
    echo "   2. Verify config files have correct values"
    echo "   3. Check port availability: netstat -tlnp | grep 8000"
    echo ""
    exit 1
fi