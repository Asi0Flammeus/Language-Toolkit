# Language Toolkit API

A REST API for the Language Toolkit providing document processing, translation, transcription, and video creation capabilities.

## Features

- **Advanced PPTX Translation**: Translate PowerPoint presentations with **full formatting preservation** - fonts, colors, styles, typography
- **Text Translation**: Translate text files using DeepL API
- **Audio Transcription**: Convert audio files to text using OpenAI Whisper
- **PPTX Conversion**: Convert PowerPoint files to PDF or PNG images
- **Text-to-Speech**: Generate audio from text files using ElevenLabs
- **Video Merging**: Combine audio and images into videos
- **Smart Downloads**: Single files download directly, multiple files as ZIP
- **Individual File Downloads**: Download specific files from multi-file results
- **Asynchronous Processing**: Handle long-running tasks with progress tracking

## Installation

1. Install API-specific dependencies:
```bash
pip install -r api_requirements.txt
```

2. Configure API keys in `api_keys.json`:
```json
{
    "openai": "your-openai-api-key",
    "deepl": "your-deepl-api-key", 
    "elevenlabs": "your-elevenlabs-api-key",
    "convertapi": "your-convertapi-secret"
}
```

3. Configure authentication tokens in `auth_tokens.json`:
```json
{
    "tokens": [
        "token_admin_abc123def456",
        "token_user_xyz789uvw012",
        "token_service_mno345pqr678"
    ]
}
```
*Copy from `auth_tokens.json.example` and customize as needed.*

## Running the API

Start the server:
```bash
python api_server.py
```

Or with uvicorn directly:
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Core Endpoints

- `GET /` - API information and available endpoints
- `GET /health` - Health check
- `GET /tasks` - List all active tasks
- `GET /tasks/{task_id}` - Get task status
- `DELETE /tasks/{task_id}` - Clean up task and temporary files
- `GET /download/{task_id}` - Download task results

### Processing Endpoints

#### PPTX Translation
```
POST /translate/pptx
```
- **Files**: Upload PPTX files
- **Form Data**: 
  - `source_lang`: Source language code (e.g., "en")
  - `target_lang`: Target language code (e.g., "fr")

#### Text Translation
```
POST /translate/text
```
- **Files**: Upload TXT files
- **Form Data**:
  - `source_lang`: Source language code
  - `target_lang`: Target language code

#### Audio Transcription  
```
POST /transcribe/audio
```
- **Files**: Upload audio files (MP3, WAV, M4A, etc.)

#### PPTX Conversion
```
POST /convert/pptx
```
- **Files**: Upload PPTX files
- **Form Data**:
  - `output_format`: "pdf" or "png"

#### Text-to-Speech
```
POST /tts
```
- **Files**: Upload TXT files (must contain voice name in filename)

#### Text Translation from S3
```
POST /translate/text_s3
```
- **JSON Body**:
  - `input_keys`: Array of S3 object keys for the input TXT files
  - `output_prefix`: (Optional) Destination S3 prefix for translated files
  - `source_lang`: Source language code (e.g., "en")
  - `target_lang`: Target language code (e.g., "fr")

#### Course Translation from S3
```
POST /translate/course_s3
```
- **JSON Body**:
  - `course_id`: Unique identifier for the course
  - `source_lang`: Current language present in S3 folder
  - `target_langs`: Array of target language codes (e.g., ["fr", "it"])
  - `output_prefix`: (Optional) Root prefix where translated course will be written

#### PPTX Translation from S3
```
POST /translate/pptx_s3
```
- **JSON Body**:
  - `input_keys`: Array of S3 object keys for the input PPTX files
  - `output_prefix`: (Optional) Destination S3 prefix for translated files
  - `source_lang`: Source language code (e.g., "en")
  - `target_lang`: Target language code (e.g., "fr")

#### Audio Transcription from S3
```
POST /transcribe/audio_s3
```
- **JSON Body**:
  - `input_keys`: Array of S3 object keys for the input audio files
  - `output_prefix`: (Optional) Destination S3 prefix for transcription results

## Usage Examples

### Using curl

1. **Translate a PPTX file**:
```bash
curl -X POST "http://localhost:8000/translate/pptx" \
  -H "Authorization: Bearer token_admin_abc123def456" \
  -F "source_lang=en" \
  -F "target_lang=fr" \
  -F "files=@presentation.pptx"
```

2. **Check task status**:
```bash
curl -H "Authorization: Bearer token_admin_abc123def456" \
  "http://localhost:8000/tasks/{task_id}"
```

3. **Download results**:
```bash
# Download all results (single file directly, multiple files as ZIP)
curl -H "Authorization: Bearer token_admin_abc123def456" \
  -O "http://localhost:8000/download/{task_id}"

# Download specific file by index (0-based)
curl -H "Authorization: Bearer token_admin_abc123def456" \
  -O "http://localhost:8000/download/{task_id}/0"
```

4. **Translate a TXT file stored in S3**:
```bash
curl -X POST "http://localhost:8000/translate/text_s3" \
  -H "Authorization: Bearer token_admin_abc123def456" \
  -H "Content-Type: application/json" \
  -d '{
        "input_keys": ["bucket/folder/document.txt"],
        "output_prefix": "translated/",
        "source_lang": "en",
        "target_lang": "fr"
      }'
```

5. **Translate a PPTX stored in S3**:
```bash
curl -X POST "http://localhost:8000/translate/pptx_s3" \
  -H "Authorization: Bearer token_admin_abc123def456" \
  -H "Content-Type: application/json" \
  -d '{
        "input_keys": ["bucket/folder/presentation.pptx"],
        "output_prefix": "translated/",
        "source_lang": "en",
        "target_lang": "fr"
      }'
```

6. **Translate an entire course from S3**:
```bash
curl -X POST "http://localhost:8000/translate/course_s3" \
  -H "Authorization: Bearer token_admin_abc123def456" \
  -H "Content-Type: application/json" \
  -d '{
        "course_id": "cad798e6-3acf-11f0-b82c-771d758cf407",
        "source_lang": "en",
        "target_langs": ["fr", "it"],
        "output_prefix": "translated/"
      }'
```

7. **Transcribe an audio file stored in S3**:
```bash
curl -X POST "http://localhost:8000/transcribe/audio_s3" \
  -H "Authorization: Bearer token_admin_abc123def456" \
  -H "Content-Type: application/json" \
  -d '{
        "input_keys": ["bucket/folder/lecture.mp3"],
        "output_prefix": "transcripts/"
      }'
```

### Using Python requests

```python
import requests

# Setup authentication
headers = {'Authorization': 'Bearer token_admin_abc123def456'}

# Upload file for translation
files = {'files': open('presentation.pptx', 'rb')}
data = {'source_lang': 'en', 'target_lang': 'fr'}

response = requests.post(
    'http://localhost:8000/translate/pptx', 
    files=files, 
    data=data,
    headers=headers
)

task_id = response.json()['task_id']

# Check status
status_response = requests.get(
    f'http://localhost:8000/tasks/{task_id}',
    headers=headers
)
print(status_response.json())

# Download when complete
if status_response.json()['status'] == 'completed':
    download_response = requests.get(
        f'http://localhost:8000/download/{task_id}',
        headers=headers
    )
    
    # Save with proper extension based on Content-Type
    content_type = download_response.headers.get('content-type', '')
    if 'presentation' in content_type:
        filename = 'translated_presentation.pptx'
    elif 'application/zip' in content_type:
        filename = 'results.zip'
    else:
        filename = 'result.file'
    
    with open(filename, 'wb') as f:
        f.write(download_response.content)
```

## Advanced PPTX Translation

The API provides **professional-grade PPTX translation** that preserves all formatting:

### ✅ **Complete Formatting Preservation**
- **Fonts**: Names, sizes, styles maintained
- **Colors**: RGB and theme colors preserved  
- **Typography**: Bold, italic, underline styles
- **Layout**: Paragraph spacing, alignment, indentation
- **Structure**: Text frames, runs, paragraph levels

### 🎯 **Same Quality as GUI App**
The API uses the same advanced translation engine as the desktop application, ensuring identical results between interfaces.

### 📊 **Professional Results**
- Maintains original presentation design
- Preserves corporate branding and styling
- Ready for professional use without reformatting

## Task Management

The API uses asynchronous task processing:

1. **Submit** a processing request → Get a `task_id`
2. **Poll** the task status using the `task_id`
3. **Download** results when status is "completed"
4. **Clean up** the task when done

### Task Status Values

- `pending`: Task queued but not started
- `running`: Task currently processing
- `completed`: Task finished successfully
- `failed`: Task encountered an error

## Error Handling

The API returns standard HTTP status codes:

- `200`: Success
- `400`: Bad Request (invalid parameters)
- `404`: Not Found (task or file not found)
- `422`: Validation Error
- `500`: Internal Server Error

Error responses include details:
```json
{
    "detail": "Error description"
}
```

## Security Considerations

For production deployment:

1. **Authentication**: Add API key authentication
2. **Rate Limiting**: Implement request rate limiting  
3. **File Validation**: Enhanced file type and size validation
4. **HTTPS**: Use HTTPS in production
5. **Resource Limits**: Set memory and processing limits
6. **Monitoring**: Add logging and monitoring

## Deployment

### Docker Deployment

Create a `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .
RUN pip install -r api_requirements.txt

EXPOSE 8000
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Production Deployment

For production, consider:
- **Gunicorn** with uvicorn workers
- **Nginx** as reverse proxy
- **Docker** containerization
- **Load balancing** for multiple instances
- **Database** for task persistence
- **Redis** for task queues

Example with Gunicorn:
```bash
gunicorn api_server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Supported File Formats

- **PPTX Translation**: .pptx files
- **Text Translation**: .txt files
- **Audio Transcription**: .wav, .mp3, .m4a, .webm, .mp4, .mpga, .mpeg
- **PPTX Conversion**: .pptx files → PDF/PNG
- **Text-to-Speech**: .txt files (with voice name in filename)

## API Limits

Current implementation limits:
- **File Size**: 25MB per file (adjustable)
- **Concurrent Tasks**: Limited by server resources
- **Audio Length**: 20MB per audio file (API limitation)

## Support

For issues and questions:
1. Check the interactive API documentation at `/docs`
2. Review the logs for detailed error information
3. Ensure all required API keys are configured