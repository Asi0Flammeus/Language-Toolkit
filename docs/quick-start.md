# 🚀 Quick Start Commands

## Option 1: Using the Start Script (Easiest)

```bash
cd Language-Toolkit
./start_app.sh     # Linux/Mac
start_app.bat      # Windows
```

## Option 2: Manual Commands

### GUI Application:

```bash
cd Language-Toolkit
source env/bin/activate  # Linux/Mac
# or .\env\Scripts\activate  # Windows
python main.py
```

### API Server:

```bash
cd Language-Toolkit
source env/bin/activate  # Linux/Mac
# or .\env\Scripts\activate  # Windows
python api_server.py
```

## 🔗 Access Points

- **GUI Application**: Desktop interface
- **API Server**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 🔑 Authentication

For API access, configure client credentials in `.env` file:
```bash
# OAuth2 Client Credentials
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
```

Then obtain an access token using the `/auth/token` endpoint.

## 🧪 Quick Test - GUI

1. Launch the GUI application
2. Select "Text Translation" tab
3. Choose a text file to translate
4. Select source and target languages
5. Click "Process"
6. Check output directory for results

## 🧪 Quick Test - API

1. Open http://localhost:8000/docs
2. Try the `/health` endpoint
3. Use the "Authorize" button with your token
4. Test the `/translate/text` endpoint
5. Monitor task progress via `/tasks/{task_id}`

## 🛑 Stop Services

Press `Ctrl+C` in each terminal

## 📝 Notes

- First run will install dependencies (may take a few minutes)
- Make sure your API keys are configured in `.env` file
- Voice names must match those in `elevenlabs_voices.json`
