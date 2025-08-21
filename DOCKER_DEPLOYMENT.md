# Docker Deployment Guide

This guide covers deploying the Language Toolkit API using Docker with proper configuration and health checks.

## 🚀 Quick Start

### 1. Validate Configuration
```bash
./docker-validate.sh
```

### 2. Deploy with Docker Compose
```bash
./docker-deploy.sh
```

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+ (or docker-compose 1.29+)
- Required configuration files (auto-created from examples if missing)

## 🔧 Configuration Files

The deployment requires these configuration files (created automatically from examples):

### Required Files
- `api_keys.json` - API keys for external services
- `auth_tokens.json` - Authentication tokens  
- `client_credentials.json` - OAuth client credentials

### Directory Structure
```
Language-Toolkit/
├── docker/
│   ├── gunicorn.conf.py    # Gunicorn configuration
│   └── entrypoint.sh       # Container entrypoint script
├── logs/                   # Application logs
├── temp/                   # Temporary files
├── uploads/                # File uploads
└── ssl/                    # SSL certificates (optional)
```

## 🐳 Docker Configuration

### Production Dockerfile
- Uses `Dockerfile.prod` for optimized multi-stage build
- Runs as non-root user for security
- Includes health checks and proper signal handling

### Docker Compose Services
- **API Container**: Main application server
- **Nginx Container**: Reverse proxy and load balancer

## 🏥 Health Checks

### Container Health Check
```bash
curl -f http://localhost:8000/health
```

### Expected Response
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "services": {
    "s3": "healthy",
    "deepl": "healthy", 
    "openai": "healthy",
    "elevenlabs": "healthy",
    "convertapi": "healthy"
  }
}
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Missing Configuration Files
**Error**: `WARNING: /app/client_credentials.json not found`

**Solution**: 
```bash
cp client_credentials.json.example client_credentials.json
# Edit with your actual values
```

#### 2. Health Check Failures
**Error**: Container marked as unhealthy

**Steps**:
1. Check container logs: `docker logs language-toolkit-api`
2. Verify configuration files have valid JSON
3. Ensure API keys are correctly set
4. Test health endpoint manually

#### 3. Port Already in Use
**Error**: `bind: address already in use`

**Solutions**:
```bash
# Check what's using the port
netstat -tlnp | grep 8000

# Stop existing containers
docker-compose down

# Or use different ports in docker-compose.yml
```

#### 4. Permission Issues
**Error**: Permission denied accessing files

**Solution**:
```bash
# Fix permissions
sudo chown -R $USER:$USER logs temp uploads
chmod 755 docker/entrypoint.sh
```

### Deployment Validation

Run the validation script to check all requirements:
```bash
./docker-validate.sh
```

### Manual Deployment Steps

If the automated script fails, deploy manually:

```bash
# 1. Create required directories
mkdir -p logs temp uploads docker

# 2. Copy configuration files
cp api_keys.json.example api_keys.json
cp auth_tokens.json.example auth_tokens.json  
cp client_credentials.json.example client_credentials.json

# 3. Edit configuration files with real values
nano api_keys.json
nano client_credentials.json

# 4. Build and start
docker-compose build --no-cache
docker-compose up -d

# 5. Check health
docker-compose ps
curl http://localhost:8000/health
```

## 📊 Monitoring

### Container Status
```bash
docker-compose ps
```

### Real-time Logs
```bash
docker-compose logs -f api
```

### Resource Usage
```bash
docker stats language-toolkit-api
```

### Health Monitoring
```bash
# Watch health endpoint
watch -n 5 'curl -s http://localhost:8000/health | jq'
```

## 🔒 Security Considerations

### Container Security
- Runs as non-root user (`appuser`)
- Minimal base image (python:3.11-slim)
- No unnecessary packages installed
- Read-only configuration file mounts

### Network Security
- Uses custom Docker network
- Nginx proxy for additional security
- SSL/TLS termination at proxy level

### Secret Management
- Configuration files mounted as read-only
- No secrets in environment variables
- Example files provided for template

## 🌐 Production Deployment

### With SSL/Domain
```bash
# Update nginx configuration
sed -i 's/your-domain.com/yourdomain.com/g' nginx.conf

# Generate SSL certificates (Let's Encrypt)
certbot certonly --standalone -d yourdomain.com

# Copy certificates
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem

# Deploy with SSL
docker-compose up -d
```

### Environment-Specific Configs
Create environment-specific compose files:
- `docker-compose.prod.yml`
- `docker-compose.staging.yml`
- `docker-compose.dev.yml`

## 🔄 Updates & Maintenance

### Updating the Application
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# Verify health
curl http://localhost:8000/health
```

### Log Rotation
```bash
# Rotate logs manually
docker-compose exec api logrotate /etc/logrotate.conf

# Or restart container to clear logs
docker-compose restart api
```

### Backup Configuration
```bash
# Backup important files
tar -czf backup-$(date +%Y%m%d).tar.gz \
  api_keys.json auth_tokens.json client_credentials.json \
  logs/ docker-compose.yml nginx.conf
```

## 📞 Support

If you encounter issues:
1. Check this troubleshooting guide
2. Run `./docker-validate.sh` to verify setup
3. Review container logs: `docker logs language-toolkit-api`
4. Test health endpoint: `curl http://localhost:8000/health`

For additional help, check the main deployment documentation or raise an issue.