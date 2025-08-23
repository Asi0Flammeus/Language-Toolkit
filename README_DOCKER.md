# 🚀 Docker Deployment - Super Simple!

## Two Ways to Deploy

### 1️⃣ Local/Testing (No domain needed)

```bash
# Just run this one command:
./deploy.sh

# Access at: http://localhost:8000/docs
```

### 2️⃣ Production Server (With your domain)

```bash
# Step 1: Start the services
docker-compose -f docker-compose.server.yml up -d

# Step 2: Get SSL certificate (replace api.example.com with YOUR domain)
sudo apt install certbot
sudo certbot certonly --standalone -d api.example.com

# Step 3: Copy certificates
mkdir -p ssl
sudo cp /etc/letsencrypt/live/api.example.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/api.example.com/privkey.pem ssl/key.pem
sudo chown $USER:$USER ssl/*

# Step 4: Restart to load SSL
docker-compose -f docker-compose.server.yml restart nginx

# ✅ Access at: https://api.example.com/docs
```

## The Only Config You Need (.env)

```env
# Just add your API keys:
OPENAI_API_KEY=sk-...
DEEPL_API_KEY=...

# Optional S3:
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET=my-bucket

```

## Useful Commands

```bash
docker-compose logs -f     # View logs
docker-compose restart      # Restart
docker-compose down         # Stop
```

