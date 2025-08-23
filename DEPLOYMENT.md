# Language Toolkit - Deployment Guide

## Overview

This guide provides instructions for deploying the Language Toolkit API using Docker. We offer two deployment scenarios:

1. **Local Development** - Quick setup for testing and development
2. **Production Deployment** - Full production setup with SSL, domain name, and security features

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Linux/Unix environment (Ubuntu 20.04+ recommended for production)
- Domain name (for production deployment)
- API keys for enabled services (OpenAI, DeepL, ElevenLabs, etc.)

## Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/Language-Toolkit.git
cd Language-Toolkit

# Run the local deployment script
./deploy-local.sh

# Access the API
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Production Deployment

```bash
# On your production server
git clone https://github.com/yourusername/Language-Toolkit.git
cd Language-Toolkit

# Run the production deployment script
./deploy-production.sh your-domain.com admin@your-domain.com

# Access the API
# API: https://your-domain.com
# Docs: https://your-domain.com/docs
```

## Configuration

### Environment Variables

All configuration is managed through environment variables. Copy `.env.example` to `.env` (or `.env.production` for production) and configure:

#### Required API Keys

```env
# At least one translation service is required
OPENAI_API_KEY=your-openai-key
DEEPL_API_KEY=your-deepl-key
ELEVENLABS_API_KEY=your-elevenlabs-key
CONVERTAPI_KEY=your-convertapi-key
```

#### Storage Configuration

Choose one of the following storage options:

**Option 1: AWS S3**
```env
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=your-bucket-name
```

**Option 2: S3-Compatible Storage (MinIO, DigitalOcean Spaces, etc.)**
```env
S3_ENDPOINT=https://your-s3-endpoint.com
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_REGION=us-east-1
S3_BUCKET=your-bucket-name
```

#### Security Settings

```env
# Change this in production!
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=60

# CORS settings (restrict in production)
ALLOWED_ORIGINS=https://your-frontend.com
```

#### Resource Limits

```env
MAX_FILE_SIZE=104857600      # 100MB
MAX_PPTX_SIZE=52428800       # 50MB
MAX_AUDIO_SIZE=209715200     # 200MB
MAX_TEXT_SIZE=10485760       # 10MB
```

## Deployment Methods

### Method 1: Using Deployment Scripts (Recommended)

#### Local Development

The `deploy-local.sh` script handles:
- Environment setup
- Docker image building
- Service startup
- Health checks

```bash
./deploy-local.sh
```

#### Production Deployment

The `deploy-production.sh` script handles:
- SSL certificate setup (Let's Encrypt or self-signed)
- Nginx reverse proxy configuration
- Firewall configuration
- Service deployment
- Health checks

```bash
# With Let's Encrypt SSL (recommended)
./deploy-production.sh api.example.com admin@example.com letsencrypt

# With self-signed SSL (for testing)
./deploy-production.sh api.example.com admin@example.com self-signed

# With existing SSL certificates
./deploy-production.sh api.example.com admin@example.com existing
```

### Method 2: Manual Docker Compose

#### Local Development

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### Production Deployment

```bash
# Copy environment file
cp .env.example .env.production
# Edit .env.production with your configuration

# Build and start services
docker-compose -f docker-compose.production.yml up -d

# View logs
docker-compose -f docker-compose.production.yml logs -f

# Stop services
docker-compose -f docker-compose.production.yml down
```

## SSL Certificate Management

### Let's Encrypt (Recommended for Production)

The production deployment script automatically sets up Let's Encrypt certificates with auto-renewal via cron job.

Manual setup:
```bash
# Obtain certificate
certbot certonly --webroot --webroot-path=./nginx/html \
  --email admin@example.com --agree-tos --no-eff-email \
  -d api.example.com

# Copy certificates
cp /etc/letsencrypt/live/api.example.com/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/api.example.com/privkey.pem nginx/ssl/
cp /etc/letsencrypt/live/api.example.com/chain.pem nginx/ssl/
```

### Self-Signed Certificates (Development/Testing)

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=api.example.com"
```

### Using Existing Certificates

Place your certificates in `nginx/ssl/`:
- `fullchain.pem` - Full certificate chain
- `privkey.pem` - Private key
- `chain.pem` - Certificate chain (optional)

## Advanced Features

### Enable Redis Caching

```bash
# Start with Redis caching
docker-compose -f docker-compose.production.yml --profile with-cache up -d
```

### Enable Monitoring (Prometheus + Grafana)

```bash
# Start with monitoring stack
docker-compose -f docker-compose.production.yml --profile monitoring up -d

# Access:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

### Scaling

For horizontal scaling, modify `docker-compose.production.yml`:

```yaml
services:
  api:
    deploy:
      replicas: 3
```

Then use a load balancer or Docker Swarm mode.

## Maintenance

### Updating the Application

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d
```

### Backup

```bash
# Backup uploads and logs
tar -czf backup-$(date +%Y%m%d).tar.gz uploads/ logs/

# Backup Docker volumes
docker run --rm -v language-toolkit_uploads:/data -v $(pwd):/backup \
  alpine tar czf /backup/uploads-backup.tar.gz -C /data .
```

### Monitoring

#### View Logs
```bash
# All services
docker-compose -f docker-compose.production.yml logs -f

# Specific service
docker-compose -f docker-compose.production.yml logs -f api
docker-compose -f docker-compose.production.yml logs -f nginx
```

#### Health Checks
```bash
# Local
curl http://localhost:8000/health

# Production
curl https://api.example.com/health
```

#### Container Status
```bash
docker-compose -f docker-compose.production.yml ps
```

## Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process or change port in .env
PORT=8001
```

#### 2. Permission Denied
```bash
# Fix permissions
sudo chown -R $USER:$USER logs/ temp/ uploads/
chmod 755 logs/ temp/ uploads/
```

#### 3. SSL Certificate Issues
```bash
# Check certificate validity
openssl x509 -in nginx/ssl/fullchain.pem -text -noout

# Test SSL connection
openssl s_client -connect api.example.com:443
```

#### 4. API Not Responding
```bash
# Check container status
docker-compose -f docker-compose.production.yml ps

# Check logs
docker-compose -f docker-compose.production.yml logs api

# Restart services
docker-compose -f docker-compose.production.yml restart
```

#### 5. Out of Memory
```bash
# Check memory usage
docker stats

# Increase memory limits in docker-compose.production.yml
deploy:
  resources:
    limits:
      memory: 4G
```

### Debug Mode

Enable debug mode in `.env`:
```env
DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

## Security Best Practices

1. **Use Strong Secrets**
   - Generate secure SECRET_KEY: `openssl rand -hex 32`
   - Use strong passwords for all services

2. **Restrict CORS**
   ```env
   ALLOWED_ORIGINS=https://your-frontend.com
   ```

3. **Configure Firewall**
   ```bash
   sudo ufw allow 22/tcp   # SSH
   sudo ufw allow 80/tcp   # HTTP
   sudo ufw allow 443/tcp  # HTTPS
   sudo ufw enable
   ```

4. **Regular Updates**
   ```bash
   # Update system packages
   sudo apt update && sudo apt upgrade

   # Update Docker images
   docker-compose -f docker-compose.production.yml pull
   docker-compose -f docker-compose.production.yml build --no-cache
   ```

5. **Enable Rate Limiting**
   - Configured in nginx.production.conf
   - Adjust limits based on your needs

6. **Use HTTPS Only**
   - Production deployment enforces HTTPS
   - HTTP automatically redirects to HTTPS

## Migration from Old Setup

If you're migrating from the old configuration using `api_keys.json`:

1. **Export existing keys** from `api_keys.json`
2. **Add them to `.env`** file
3. **Remove old configuration files**:
   ```bash
   rm api_keys.json auth_tokens.json client_credentials.json
   ```
4. **Use new deployment scripts**

## Support

For issues or questions:
- Check logs: `docker-compose logs`
- Review this documentation
- Check environment variables in `.env`
- Ensure all prerequisites are installed

## License

See LICENSE file in the repository root.