# Testing the Language Toolkit API

This guide shows you how to test your Language Toolkit API using multiple approaches: a React web interface, command-line tools, and automated scripts.

## Prerequisites

1. **Start the API server:**
```bash
python api_server.py
```
The API will be available at `http://localhost:8000`

2. **Verify API is running:**
```bash
curl http://localhost:8000/health
```

3. **Ensure authentication tokens are configured:**
The API requires authentication tokens. Make sure `auth_tokens.json` exists:
```bash
cp auth_tokens.json.example auth_tokens.json
# Edit auth_tokens.json to customize tokens if needed
```

## Testing Methods

### 1. 🌐 React Web Interface (Recommended)

The React app provides a comprehensive visual interface for testing all API endpoints.

#### Setup:
```bash
cd api-test-app
npm install
npm start
```

The React app will open at `http://localhost:3000` and includes:

- **🎯 Real-time API health monitoring**
- **📤 File upload interfaces** for each endpoint
- **⏱️ Live task status tracking** with auto-refresh
- **📥 One-click result downloads**
- **🧹 Task cleanup management**
- **🎨 Beautiful, responsive UI**

#### Features:
- **PPTX Translation**: Test with `ECO102-FR-V001-2.1.pptx` or `btc204-v001-1.1.pptx`
- **Text Translation**: Use `.txt` files from `test-app/btc204/` folder
- **Audio Transcription**: Test with `.mp3` files like `test_Loic.mp3`
- **PPTX Conversion**: Convert presentations to PDF or PNG
- **Text-to-Speech**: Convert text files to audio
- **Drag & Drop**: Easy file uploads with drag-and-drop support

### 2. 🚀 Quick Command Line Testing

Use the provided test script for rapid API testing:

```bash
./test_api.sh
```

This script provides:
- ✅ Automatic API health check
- 📁 List of available test files
- 🎯 Pre-configured curl commands
- 🤖 Interactive testing mode

### 3. 📝 Manual curl Commands

#### Test PPTX Translation:
```bash
curl -X POST "http://localhost:8000/translate/pptx" \
  -F "source_lang=en" \
  -F "target_lang=fr" \
  -F "files=@test-app/ECO102-FR-V001-2.1.pptx"
```

#### Test Text Translation:
```bash
curl -X POST "http://localhost:8000/translate/text" \
  -F "source_lang=en" \
  -F "target_lang=fr" \
  -F "files=@test-app/btc204/00.txt"
```

#### Test Audio Transcription:
```bash
curl -X POST "http://localhost:8000/transcribe/audio" \
  -F "files=@test-app/btc204/00.mp3"
```

#### Test PPTX Conversion:
```bash
curl -X POST "http://localhost:8000/convert/pptx" \
  -F "output_format=pdf" \
  -F "files=@test-app/ECO102-FR-V001-2.1.pptx"
```

#### Check Task Status:
```bash
curl "http://localhost:8000/tasks/TASK_ID"
```

#### Download Results:
```bash
curl -O "http://localhost:8000/download/TASK_ID"
```

### 4. 📖 Interactive API Documentation

FastAPI provides automatic interactive documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

These interfaces allow you to:
- 🔍 Explore all available endpoints
- 📝 View request/response schemas
- 🧪 Test endpoints directly in the browser
- 📋 Copy curl commands

## Test Files Available

Your `test-app` folder contains these test files:

### PPTX Files (for translation/conversion):
- `ECO102-FR-V001-2.1.pptx` - Economics presentation
- `btc204-v001-1.1.pptx` - Bitcoin course presentation
- `ECO102-FR-V001-2.1_en-US.pptx` - English version
- `ECO102-FR-V001-2.1_fr.pptx` - French version
- `ECO102-FR-V001-2.1_it.pptx` - Italian version

### Text Files (for translation/TTS):
- `test-app/btc204/00.txt` through `07.txt` - Course transcripts
- `test-app/btc204/00_it.txt` - Italian transcript
- `test_Loic.txt` - Test file with voice name

### Audio Files (for transcription):
- `test-app/btc204/00.mp3` through `07.mp3` - Course audio
- `test_Loic.mp3` - Test audio file

### Image Files (for video merge):
- `test-app/ECO102-FR-V001-2.1_slides/` - PNG slides

## Testing Workflow

### Typical Test Sequence:

1. **🚀 Submit a Task**:
   - Use React app or curl to submit files
   - Get back a `task_id`

2. **⏱️ Monitor Progress**:
   - Check task status: `GET /tasks/{task_id}`
   - Watch for status changes: `pending` → `running` → `completed`

3. **📥 Download Results**:
   - When status is `completed`: `GET /download/{task_id}`
   - Results are returned as individual files or ZIP archives

4. **🧹 Cleanup**:
   - Delete task: `DELETE /tasks/{task_id}`
   - This cleans up temporary files

### Error Testing:

Test error handling with:
- **Invalid file types**: Upload `.jpg` to PPTX endpoint
- **Missing parameters**: Submit without required language codes
- **Large files**: Test file size limits
- **Invalid task IDs**: Check non-existent tasks

## Performance Testing

### Load Testing with Multiple Files:
```bash
# Upload multiple files simultaneously
curl -X POST "http://localhost:8000/translate/pptx" \
  -F "source_lang=en" \
  -F "target_lang=fr" \
  -F "files=@test-app/ECO102-FR-V001-2.1.pptx" \
  -F "files=@test-app/btc204-v001-1.1.pptx"
```

### Concurrent Requests:
```bash
# Run multiple requests in parallel
for i in {1..5}; do
  curl -X POST "http://localhost:8000/transcribe/audio" \
    -F "files=@test-app/btc204/0$((i-1)).mp3" &
done
wait
```

## Troubleshooting

### Common Issues:

1. **API Not Responding**:
   - Check if server is running: `python api_server.py`
   - Verify port 8000 is not blocked

2. **File Upload Errors**:
   - Check file paths are correct
   - Verify file extensions match endpoint requirements
   - Ensure files exist and are readable

3. **Task Status "failed"**:
   - Check API server logs for detailed errors
   - Verify API keys are configured in `api_keys.json`
   - Test with smaller files first

4. **React App Issues**:
   - Ensure API server is running first
   - Check browser console for CORS errors
   - Verify proxy configuration in `package.json`

### Debug Mode:

Run API server with debug logging:
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload --log-level debug
```

## Success Indicators

✅ **Healthy API**: Health check returns `{"status": "healthy"}`  
✅ **Successful Upload**: Returns `task_id` and status `"pending"`  
✅ **Processing**: Task status changes to `"running"`  
✅ **Completion**: Task status becomes `"completed"` with `result_files`  
✅ **Download**: Files download successfully as ZIP or individual files  

## Next Steps

After testing the API:

1. **🔒 Add Authentication**: Implement API key authentication
2. **📊 Add Monitoring**: Set up logging and metrics
3. **🐳 Containerize**: Create Docker containers for deployment
4. **🚀 Deploy**: Deploy to production environment
5. **📈 Scale**: Add load balancing and auto-scaling

## Support

If you encounter issues:
1. Check the server logs for detailed error messages
2. Verify all API keys are properly configured
3. Test with the provided sample files first
4. Use the interactive documentation at `/docs` for reference