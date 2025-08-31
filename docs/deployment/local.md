# 🚀 Local Deployment Guide

This guide will help you run the Language Toolkit API server and test app on your local machine.

## 📋 Prerequisites

- Python 3.8+
- Node.js 14+ and npm
- Git

## 🛠️ Step 1: API Server Setup

### 1.1 Clone and Navigate to Project
```bash
cd ~/asi0-repos/language_toolkit
```

### 1.2 Create Python Virtual Environment
```bash
# Create virtual environment
python3 -m venv env

# Activate virtual environment
# On Linux/Mac:
source env/bin/activate

# On Windows:
# env\Scripts\activate
```

### 1.3 Install API Dependencies
```bash
# Install API server dependencies
pip install -r api_requirements.txt

# If api_requirements.txt doesn't exist, install manually:
pip install fastapi uvicorn python-dotenv boto3 python-jose[cryptography] \
            python-multipart aiofiles requests deepl openai elevenlabs \
            convertapi pydub moviepy

# Install core dependencies
pip install -r requirements.txt
```

### 1.4 Configure Environment Variables
```bash
# Create .env file from example
cp .env.example .env 2>/dev/null || touch .env

# Edit .env file with your API keys
nano .env  # or use your favorite editor
```

Add the following to your `.env` file:
```env
# API Keys (REQUIRED - all keys must be in .env)
DEEPL_API_KEY=your_deepl_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
CONVERTAPI_SECRET=your_convertapi_secret_here

# Optional: AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket_name

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

### 1.5 Set Up Authentication

**Note:** Authentication now uses OAuth2 client credentials flow. Configure your clients in the `.env` file:

```env
# OAuth2 Client Credentials
# For single client:
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret

# For multiple clients (optional):
# CLIENT_ID_1=first-client-id
# CLIENT_SECRET_1=first-client-secret
# CLIENT_ID_2=second-client-id
# CLIENT_SECRET_2=second-client-secret
```

To obtain an access token, use the `/auth/token` endpoint with your client credentials.

## 🚀 Step 2: Start the API Server

### 2.1 Basic Start Command
```bash
# Make sure you're in the project root and venv is activated
cd ~/asi0-repos/language_toolkit
source env/bin/activate

# Start the API server
python api_server.py
```

### 2.2 Alternative: Start with Uvicorn Directly
```bash
# With auto-reload for development
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000

# Production mode (no auto-reload)
uvicorn api_server:app --host 0.0.0.0 --port 8000 --workers 4
```

### 2.3 Verify API is Running
```bash
# In a new terminal, check health endpoint
curl http://localhost:8000/health

# Or open in browser
open http://localhost:8000/docs  # Mac
xdg-open http://localhost:8000/docs  # Linux
# Or manually visit: http://localhost:8000/docs
```

You should see:
- Health check: `{"status": "healthy", "timestamp": "..."}`
- Swagger UI documentation at `/docs`

## 🎨 Step 3: Start the Test App

### 3.1 Navigate to Test App Directory
```bash
# Open a new terminal
cd ~/asi0-repos/language_toolkit/api-test-app
```

### 3.2 Install Node Dependencies
```bash
# Install dependencies (only needed first time)
npm install

# If you encounter issues, try:
npm install --force
```

### 3.3 Use the Enhanced Test App (Recommended)
```bash
# First, replace the default App.js with the enhanced version
cp src/App.enhanced.js src/App.js

# Start the test app
npm start
```

### 3.4 Alternative: Use Original Test App
```bash
# If you want to use the original simpler version
git checkout src/App.js  # Revert to original
npm start
```

The test app will automatically open at `http://localhost:3000`

## 🧪 Step 4: Test the Setup

### 4.1 Using the Test App
1. **Open the test app** at `http://localhost:3000`
2. **Check API Status** - Should show "healthy" in green
3. **Authentication** - The default token `token_admin_abc123def456` should already be filled
4. **Test an endpoint**:
   - Go to the "Test Data" tab
   - Generate a test file for "Loic" voice
   - Download the generated file
   - Go back to "API Tools" tab
   - Upload the file to Text-to-Speech section
   - Click "Convert to Speech"
   - Monitor the task in Task Manager
   - Download the MP3 result when complete

### 4.2 Using cURL Commands
```bash
# Test authentication
curl -H "Authorization: Bearer token_admin_abc123def456" \
     http://localhost:8000/tasks

# Test text-to-speech with a file
echo "Hello, this is a test for Loic voice" > test_Loic_demo.txt

curl -X POST \
     -H "Authorization: Bearer token_admin_abc123def456" \
     -F "files=@test_Loic_demo.txt" \
     http://localhost:8000/tts

# Check task status (replace TASK_ID with actual ID from response)
curl -H "Authorization: Bearer token_admin_abc123def456" \
     http://localhost:8000/tasks/TASK_ID
```

## 🔧 Troubleshooting

### Port Already in Use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9  # Mac/Linux

# Or use a different port
uvicorn api_server:app --port 8001
# Then update test app: edit API_BASE_URL in src/App.js
```

### Missing Dependencies
```bash
# For API server
pip install -r api_requirements.txt --upgrade

# For test app
cd api-test-app
rm -rf node_modules package-lock.json
npm install
```

### CORS Issues
The API server is configured to accept requests from:
- http://localhost:3000
- http://127.0.0.1:3000

If you're using a different port, update the CORS settings in `api_server.py`

### API Key Issues
1. Check that all API keys are correctly set in the `.env` file
2. Verify the keys are valid with their respective services
3. Check logs for specific API errors
4. If you have an old `api_keys.json` file, you can remove it - it's no longer used

## 📝 Quick Commands Summary

```bash
# Terminal 1: API Server
cd ~/asi0-repos/language_toolkit
source env/bin/activate
python api_server.py

# Terminal 2: Test App  
cd ~/asi0-repos/language_toolkit/api-test-app
npm start

# Terminal 3: Testing
curl http://localhost:8000/health
open http://localhost:8000/docs
open http://localhost:3000
```

## 🎯 Next Steps

1. **Test Voice Configuration**: Upload files with voice names (e.g., `test_Loic_content.txt`)
2. **Try All Endpoints**: Use the test app to try each tool
3. **Check Logs**: Monitor API server terminal for progress messages
4. **Explore API Docs**: Visit http://localhost:8000/docs for interactive API documentation

## 🚨 Important Notes

- The API server runs on port **8000** by default
- The test app runs on port **3000** by default
- Default auth token for testing: `token_admin_abc123def456`
- Voice files should include voice names from `elevenlabs_voices.json` in the filename
- All uploaded files are processed in temporary directories and cleaned up after download

Happy testing! 🎉