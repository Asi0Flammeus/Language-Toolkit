# 🚀 Super Simple Docker Deployment

## Quick Start (2 minutes)

### Step 1: Setup
```bash
# Clone the repo
git clone <your-repo>
cd Language-Toolkit

# Copy and edit .env
cp .env.example .env
# Add your API keys to .env file
```

### Step 2: Deploy

#### Option A: Local/Testing (No domain needed)
```bash
./deploy.sh
# That's it! Access at http://localhost:8000
```

#### Option B: Production Server (With domain)
```bash
# 1. First deploy without SSL
docker-compose -f docker-compose.server.yml up -d

# 2. Get SSL certificate (replace with your domain)
sudo apt install certbot
sudo certbot certonly --standalone -d api.yourdomain.com

# 3. Copy certificates
mkdir -p ssl
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*

# 4. Restart with SSL
docker-compose -f docker-compose.server.yml restart

# Access at https://api.yourdomain.com
```

## That's It! 🎉

Your API is running. Access the docs at:
- Local: http://localhost:8000/docs
- Server: https://api.yourdomain.com/docs

## Common Commands

```bash
# View logs
docker-compose logs -f

# Restart
docker-compose restart

# Stop
docker-compose down

# Rebuild after code changes
docker-compose build && docker-compose up -d
```

## Minimal .env File

You only need to add the API keys you want to use:

```env
# Just add your keys here
OPENAI_API_KEY=sk-...
DEEPL_API_KEY=...

# Optional S3 for file storage
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=my-bucket
```

## Troubleshooting

**Port in use?**
```bash
# Change port in .env
PORT=8001
```

**Not starting?**
```bash
# Check logs
docker-compose logs api
```

**Need to rebuild?**
```bash
docker-compose build --no-cache
docker-compose up -d
```

---
*That's all! No complex configuration needed. Just add your API keys and deploy.*