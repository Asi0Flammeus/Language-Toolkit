# 🚀 Language Toolkit API Production Deployment

This guide provides complete instructions for deploying the Language Toolkit API to a production server with HTTPS, SSL certificates, and proper security hardening.

## 📋 Prerequisites

### Server Requirements

- **OS**: Ubuntu 20.04+ or similar Linux distribution
- **RAM**: Minimum 4GB (8GB+ recommended for heavy processing)
- **Storage**: 20GB+ free space
- **CPU**: 2+ cores recommended
- **Network**: Public IP address and domain name

### Software Requirements

- Docker 20.10+
- Docker Compose 2.0+
- Domain name pointing to your server's IP
- Firewall access to ports 80 and 443

## 🏗️ Deployment Steps

### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Reboot to apply group changes
sudo reboot
```

### 2. Copy Application Files

Clone the repo to your server in a directory (e.g., `/opt/language-toolkit/`):

```
language-toolkit/
├── api_server.py
├── core/                 # All core modules
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── deploy.sh
├── auth_tokens.json.example
└── .env (create this)
```

### 3. Configure API Keys and Authentication

Copy `.env.example` and edit it with your actual API keys and a secure JWT token.

```bash
cp .env.example .env
nano .env
```

### 4. Deploy with Automated Script

```bash
# Make script executable
chmod +x deploy.sh

# Deploy (replace with your domain and email)
./deploy.sh yourdomain.com admin@yourdomain.com
```

The script automatically:

- ✅ Configures SSL certificates with Let's Encrypt
- ✅ Sets up Nginx reverse proxy
- ✅ Builds and starts Docker containers
- ✅ Configures automatic certificate renewal
- ✅ Sets up security headers and rate limiting

## 🔧 Manual Deployment (Alternative)

If you prefer manual setup:

### 1. Configure Domain in Nginx

```bash
# Edit nginx.conf and replace 'your-domain.com' with your domain
sed -i 's/your-domain.com/yourdomain.com/g' nginx.conf
```

### 2. Get SSL Certificates

```bash
# Install certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com

# Copy certificates
mkdir -p ssl
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*.pem
```

### 3. Build and Start

```bash
# Create directories
mkdir -p logs temp

# Build and start services
docker-compose build
docker-compose up -d
```

## 🔒 Security Features

The deployment includes:

- **SSL/TLS Encryption**: Automatic HTTPS with Let's Encrypt
- **Rate Limiting**: API endpoint protection
- **Security Headers**: XSS, CSRF, and clickjacking protection
- **File Upload Limits**: Configurable upload size restrictions
- **Container Security**: Non-root user execution
- **Network Isolation**: Docker bridge networking

## 🌐 Access Your API

After deployment:

- **API Endpoint**: `https://yourdomain.com`
- **Health Check**: `https://yourdomain.com/health`
- **Documentation**: `https://yourdomain.com/docs`
- **Interactive Docs**: `https://yourdomain.com/redoc`

## 📊 Monitoring & Management

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f nginx
```

### Service Management

```bash
# Restart services
docker-compose restart

# Stop services
docker-compose stop

# Start services
docker-compose start

# Update and rebuild
docker-compose down
docker-compose build
docker-compose up -d
```

### Check Service Status

```bash
docker-compose ps
```

## 🔧 Configuration

### Rate Limiting

Modify `nginx.conf` to adjust rate limits:

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=upload_limit:10m rate=2r/s;
```

### File Upload Limits

Adjust in `nginx.conf`:

```nginx
client_max_body_size 100M;  # Change as needed
```

### API Workers

Modify `Dockerfile` CMD line:

```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", ...]
```

## 🛡️ Firewall Configuration

```bash
# Ubuntu/Debian with ufw
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# CentOS/RHEL with firewalld
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 🔄 Automatic Updates

### SSL Certificate Renewal

Automatically configured via cron:

```bash
# Check current crontab
crontab -l

# Manual renewal test
sudo certbot renew --dry-run
```

### System Updates

Consider setting up automatic security updates:

```bash
sudo apt install unattended-upgrades
sudo dpkg-reconfigure unattended-upgrades
```

## 🚨 Troubleshooting

### Common Issues

1. **SSL Certificate Error**

   ```bash
   # Check certificate status
   sudo certbot certificates

   # Manually renew
   sudo certbot renew
   docker-compose restart nginx
   ```

2. **Service Won't Start**

   ```bash
   # Check logs
   docker-compose logs api

   # Check configuration
   docker-compose config
   ```

3. **API Keys Not Working**

   ```bash
   # Verify API keys file
   cat .env

   # Restart API service
   docker-compose restart api
   ```

4. **High Memory Usage**

   ```bash
   # Monitor resource usage
   docker stats

   # Reduce worker count in Dockerfile
   --workers 2  # Instead of 4
   ```

### Health Checks

```bash
# API health
curl https://yourdomain.com/health

# SSL certificate check
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Service status
systemctl status docker
docker-compose ps
```

## 📈 Performance Optimization

### Production Tweaks

1. **Increase Worker Processes**

   ```dockerfile
   # In Dockerfile, adjust based on CPU cores
   --workers 8  # 2x CPU cores
   ```

2. **Add Redis Cache** (Optional)

   ```yaml
   # In docker-compose.yml
   redis:
     image: redis:alpine
     restart: unless-stopped
   ```

3. **Database for Task Storage** (Optional)
   Consider PostgreSQL for persistent task storage in high-volume scenarios.

## 📞 Support

- Check logs first: `docker-compose logs -f`
- Verify configuration: `docker-compose config`
- Test connectivity: `curl https://yourdomain.com/health`
- Monitor resources: `docker stats`

## 🎉 Success!

Your Language Toolkit API is now running in production with:

- ✅ HTTPS encryption
- ✅ Automatic SSL renewal
- ✅ Security hardening
- ✅ Rate limiting
- ✅ Health monitoring
- ✅ Log management

