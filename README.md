
# Language-Toolkit

A Python-based GUI application for managing various language-related tasks, including PPTX translation, text file translation, and audio transcription.

## Features

- **PPTX Translation**: Translate PowerPoint presentations while preserving formatting
- **Text Translation**: Translate text files with support for multiple languages
- **Audio Transcription**: Transcribe audio files using OpenAI's Whisper API
- **Batch Processing**: Process multiple files or entire directories recursively
- **Progress Tracking**: Real-time progress updates and error reporting
- **Drag & Drop**: Support for drag and drop file selection

## Prerequisites

- Python 3.8 or higher
- API keys for:
  - DeepL (for translation)
  - OpenAI (for audio transcription)

## Installation

### macOS

1. Install Homebrew (if not already installed):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

2. Install Git:
```bash
brew install git
```

3. Install Python 3.8+:
```bash
brew install python@3.11
```

4. Clone the repository:
```bash
git clone https://github.com/Asi0Flammeus/Language-Toolkit.git
cd Language-Toolkit
```

5. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

6. Install required packages:
```bash
pip install -r requirements.txt
```

### Windows

1. Install Python 3.8+ from [python.org](https://www.python.org/downloads/)

2. Clone the repository:
```bash
git clone https://github.com/Asi0Flammeus/Language-Toolkit.git
cd Language-Toolkit
```

3. Create and activate a virtual environment:
```bash
python -m venv venv
.\venv\Scripts\activate
```

4. Install required packages:
```bash
pip install -r requirements.txt
```

### Ubuntu

1. Install Python and required system packages:
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv python3-tk
```

2. Clone the repository:
```bash
git clone https://github.com/Asi0Flammeus/Language-Toolkit.git
cd Language-Toolkit
```

3. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

4. Install required packages:
```bash
pip install -r requirements.txt
```

## Configuration

1. Create necessary configuration files in the project root:

`supported_languages.json`:
```json
{
    "source_languages": {
        "en": "English",
        "fr": "French",
        "de": "German"
    },
    "target_languages": {
        "en": "English",
        "fr": "French",
        "de": "German"
    }
}
```

`api_keys.json`:
```json
{
    "deepl": "your-deepl-api-key",
    "openai": "your-openai-api-key"
}
```

## Usage

### Quick Start (Recommended)

Use the provided startup scripts that automatically handle git updates, virtual environment activation, and dependency installation:

**Linux/Mac:**
```bash
./start_app.sh
```

**Windows:**
```batch
start_app.bat
```

These scripts will:
1. Pull the latest changes from git
2. Activate the virtual environment
3. Update all dependencies from requirements.txt
4. Start the application

### Manual Start

If you prefer to start the application manually:
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# Start the application
python main.py
```

### Using the Application

1. Select the desired tool tab (PPTX Translation, Text Translation, or Audio Transcription)

2. Choose processing mode:
   - Single File: Process individual files
   - Folder (Recursive): Process all supported files in a directory and its subdirectories

3. Select source and target languages (for translation tools)

4. Choose input files/folder and output directory

5. Click "Process" to start the operation

## Supported File Types

- PPTX Translation: `.pptx`
- Text Translation: `.txt`
- Audio Transcription: `.wav`, `.mp3`, `.m4a`, `.webm`, `.mp4`, `.mpga`, `.mpeg`

## API Server

The Language Toolkit includes a FastAPI server that provides REST API endpoints for all tools.

### Quick Start

1. Configure your `.env` file with API keys and authentication credentials (see `.env.example`)

2. Start the server:
```bash
python api_server.py
```

3. The API will be available at `http://localhost:8000`
   - API documentation: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/health`

### Authentication

The API uses JWT-based authentication. See [README_AUTH.md](README_AUTH.md) for detailed authentication setup and usage.

### Documentation

- [API Documentation](README_API.md) - Complete API endpoints reference
- [Authentication Guide](README_AUTH.md) - Authentication setup and examples
- [Docker Deployment](README_DOCKER.md) - Docker deployment instructions
- [Testing Guide](README_TESTING.md) - API testing documentation

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
