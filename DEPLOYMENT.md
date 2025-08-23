# Language Toolkit - Simple Docker Deployment

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Domain name (for production with SSL)

## Quick Start

### 1. Setup Environment

```bash
# Clone the repository
git clone https://github.com/Asi0Flammeus/Language-Toolkit.git
cd Language-Toolkit

# Create .env file
cp .env.example .env

# Edit .env and add your API keys (only add the ones you need)
nano .env
```

### 2. Deploy

#### Option A: Local/Development (No domain needed)

```bash
# Simple one-command deployment
./deploy.sh

# Access at: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

#### Option B: Production with Domain & SSL

```bash
# Step 1: Deploy with nginx (replace your-domain.com with your actual domain)
docker-compose -f docker-compose.server.yml up -d

# Step 2: Install certbot if not already installed
sudo apt update
sudo apt install certbot -y

# Step 3: Get SSL certificate (replace with your domain and email)
sudo certbot certonly --standalone \
  -d api.your-domain.com \
  --email admin@your-domain.com \
  --agree-tos \
  --non-interactive

# Step 4: Copy certificates to project
mkdir -p ssl
sudo cp /etc/letsencrypt/live/api.your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/api.your-domain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*.pem

# Step 5: Restart nginx to load certificates
docker-compose -f docker-compose.server.yml restart nginx

# Access at: https://api.your-domain.com
# API Docs: https://api.your-domain.com/docs
```

## Environment Configuration

The `.env` file only needs the API keys you want to use:

```env
# API Keys (only add what you need)
OPENAI_API_KEY=sk-...
DEEPL_API_KEY=...
ELEVENLABS_API_KEY=...
CONVERTAPI_KEY=...

# AWS S3 (optional - for file storage)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=my-bucket

# Security (optional - has good defaults)
SECRET_KEY=change-me-in-production
PORT=8000
```

## SSL Certificate Auto-Renewal

Set up automatic renewal for Let's Encrypt certificates:

```bash
# Add cron job for auto-renewal
(crontab -l 2>/dev/null; echo "0 2 * * * certbot renew --quiet && cp /etc/letsencrypt/live/api.your-domain.com/*.pem /path/to/project/ssl/ && docker-compose -f docker-compose.server.yml restart nginx") | crontab -
```

## Common Commands

```bash
# View logs
docker-compose logs -f              # Local
docker-compose -f docker-compose.server.yml logs -f  # Production

# Restart services
docker-compose restart              # Local
docker-compose -f docker-compose.server.yml restart  # Production

# Stop services
docker-compose down                # Local
docker-compose -f docker-compose.server.yml down    # Production

# Rebuild after code changes
docker-compose build --no-cache
docker-compose up -d
```

## Troubleshooting

### Port Already in Use

```bash
# Change port in .env
PORT=8001
```

### Certificate Issues

```bash
# Check certificate
openssl x509 -in ssl/cert.pem -text -noout

# Test renewal
sudo certbot renew --dry-run
```

### API Not Responding

```bash
# Check container status
docker-compose ps

# Check logs
docker-compose logs api
```

### Permission Issues

```bash
# Fix permissions
sudo chown -R $USER:$USER logs/ temp/ uploads/ ssl/
chmod 755 logs/ temp/ uploads/
chmod 644 ssl/*.pem
```

## Production Security Checklist

- [ ] Change `SECRET_KEY` in `.env` to a strong random value
- [ ] Set up firewall (allow only ports 22, 80, 443)
- [ ] Use HTTPS (SSL certificates as shown above)
- [ ] Regularly update Docker images and system packages
- [ ] Monitor logs for suspicious activity

## Support

For issues:

- Check logs: `docker-compose logs`
- Verify environment variables in `.env`
- Ensure Docker and Docker Compose are installed

## License

See LICENSE file in the repository root.

