#!/bin/bash

# Simple deployment script for Language Toolkit
set -e

echo "🚀 Language Toolkit Deployment"
echo "=============================="

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Setup .env if it doesn't exist
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📝 Creating .env file..."
        cp .env.example .env
        echo "⚠️  Please edit .env and add your API keys, then run this script again."
        exit 0
    fi
fi

# Create directories
mkdir -p logs temp uploads

# Build and start
echo "🔨 Building Docker image..."
docker-compose build

echo "🚀 Starting services..."
docker-compose down 2>/dev/null || true
docker-compose up -d

# Wait for API
echo -n "⏳ Waiting for API to start"
for i in {1..30}; do
    if curl -s http://localhost:${PORT:-8000}/health > /dev/null 2>&1; then
        echo " ✅"
        break
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "✅ Deployment Complete!"
echo ""
echo "🌐 Access your API at:"
echo "   http://localhost:${PORT:-8000}"
echo "   http://localhost:${PORT:-8000}/docs (API Documentation)"
echo ""
echo "📋 Useful commands:"
echo "   docker-compose logs -f    # View logs"
echo "   docker-compose restart     # Restart"
echo "   docker-compose down        # Stop"
echo ""