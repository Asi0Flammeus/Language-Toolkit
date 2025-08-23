# 🚀 Quick Start Commands

## Option 1: Using the Start Script (Easiest)

```bash
cd ~/asi0-repos/language_toolkit
./start_local.sh
# Choose option 3 to start both services
```

## Option 2: Manual Commands

### Terminal 1 - API Server:

```bash
cd ~/asi0-repos/language_toolkit
source env/bin/activate
python api_server.py
```

### Terminal 2 - Test App:

```bash
cd ~/asi0-repos/language_toolkit/api-test-app
npm install
npm start
```

## 🔗 Access Points

- **API Server**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Test App**: http://localhost:3000

## 🔑 Default Auth Token

```
token_admin_abc123def456
```

## 🧪 Quick Test

1. Open http://localhost:3000
2. Check green "healthy" status
3. Go to "Test Data" tab
4. Click "Generate for Loic"
5. Download the file
6. Go to "API Tools" tab
7. Upload to "Text to Speech"
8. Click "Convert to Speech"
9. Download MP3 when ready

## 🛑 Stop Services

Press `Ctrl+C` in each terminal

## 📝 Notes

- First run will install dependencies (may take a few minutes)
- Make sure your API keys are configured in `.env` file
- Voice names must match those in `elevenlabs_voices.json`
