# Language Toolkit

A comprehensive Python-based application for language processing tasks, featuring both a GUI interface and REST API. The toolkit provides advanced document translation, audio transcription, text-to-speech conversion, and multimedia processing capabilities.

## 🚀 Quick Start

### GUI App

```bash
python main.py
```

### API Server

```bash
python api_server.py
```

Access points:

- **GUI Application**: Desktop interface
- **API Server**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## ✨ Features

### Core Tools

- **PPTX Translation**: Translate PowerPoint presentations with full formatting preservation
- **Text Translation**: Multi-language text file translation using DeepL
- **Audio Transcription**: Convert audio to text using OpenAI Whisper
- **Text-to-Speech**: Generate natural speech from text using ElevenLabs
- **PPTX to PDF**: Convert presentations to PDF format
- **Video Merging**: Combine audio and images into video files
- **Transcript Cleaning**: Advanced text processing and formatting
- **Reward Evaluation**: Assess text quality based on custom metrics

### Key Capabilities

- Batch processing with recursive directory support
- Real-time progress tracking
- Multi-language support (30+ languages)
- Asynchronous task processing
- Smart file handling (single files or ZIP archives)

## 🌍 Supported Languages

The Language Toolkit supports 29 languages across translation (txt/pptx) and text-to-speech (TTS) services.

### Language Support Matrix

| Language | Code | Translation Provider | TXT | PPTX | ElevenLabs TTS |
|----------|------|---------------------|-----|------|----------------|
| Czech | cs | DeepL | ✅ | ✅ | ✅ |
| German | de | DeepL | ✅ | ✅ | ✅ |
| English | en | DeepL | ✅ | ✅ | ✅ |
| Spanish | es | DeepL | ✅ | ✅ | ✅ |
| Estonian | et | DeepL | ✅ | ✅ | ❌ |
| Farsi | fa | OpenAI | ✅ | ✅ | ❌ |
| Finnish | fi | DeepL | ✅ | ✅ | ✅ |
| French | fr | DeepL | ✅ | ✅ | ✅ |
| Hindi | hi | Google | ✅ | ✅ | ✅ |
| Indonesian | id | DeepL | ✅ | ✅ | ✅ |
| Italian | it | DeepL | ✅ | ✅ | ✅ |
| Japanese | ja | DeepL | ✅ | ✅ | ✅ |
| Korean | ko | DeepL | ✅ | ✅ | ✅ |
| Norwegian | nb-NO | DeepL | ✅ | ✅ | ❌ |
| Dutch | nl | DeepL | ✅ | ✅ | ✅ |
| Polish | pl | DeepL | ✅ | ✅ | ✅ |
| Portuguese | pt | DeepL | ✅ | ✅ | ✅ |
| Rundi | rn | Google | ✅ | ✅ | ❌ |
| Romanian | ro | DeepL | ✅ | ✅ | ✅ |
| Russian | ru | DeepL | ✅ | ✅ | ✅ |
| Sinhala | si | OpenAI | ✅ | ✅ | ❌ |
| Serbian (Latin) | sr-Latn | OpenAI | ✅ | ✅ | ❌ |
| Swedish | sv | DeepL | ✅ | ✅ | ✅ |
| Swahili | sw | Google | ✅ | ✅ | ❌ |
| Thai | th | OpenAI | ✅ | ✅ | ❌ |
| Turkish | tr | DeepL | ✅ | ✅ | ✅ |
| Vietnamese | vi | Google | ✅ | ✅ | ❌ |
| Chinese Simplified | zh-Hans | DeepL | ✅ | ✅ | ✅ |
| Chinese Traditional | zh-Hant | DeepL | ✅ | ✅ | ✅ |

### Provider Summary

**Translation Providers:**
- **DeepL** (21 languages): Premium European & Asian language translation
- **Google Translate** (4 languages): Broad language coverage for Hindi, Rundi, Swahili, Vietnamese
- **OpenAI GPT-4** (4 languages): Context-aware translation for Farsi, Sinhala, Serbian, Thai

**Text-to-Speech:**
- **ElevenLabs Multilingual V2** (20 languages): Natural voice synthesis with high quality
- **Not Supported** (9 languages): Estonian, Farsi, Norwegian, Rundi, Sinhala, Serbian, Swahili, Thai, Vietnamese

### Notes

- **Translation (TXT/PPTX)**: All 29 languages supported with automatic provider selection
- **TTS**: 20 languages supported via ElevenLabs multilingual_v2 model
- **Provider Selection**: Automatic based on target language (see `language_provider.json`)
- **Configuration**: See `elevenlabs_languages.json` for TTS language mapping

## 📋 Prerequisites

- Python 3.8 or higher
- API keys for:
  - DeepL (translation)
  - OpenAI (transcription)
  - ElevenLabs (text-to-speech)
  - ConvertAPI (PDF conversion)
  - Anthropic (optional, for reward evaluation)

## 🔧 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Asi0Flammeus/Language-Toolkit.git
cd Language-Toolkit
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv env

# Activate environment
source env/bin/activate    # Linux/Mac
.\env\Scripts\activate      # Windows

# Install dependencies
pip3 install -r requirements.txt
```

### 3. Configure API Keys

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Then edit `.env` with your API keys:

```bash
# API Keys
DEEPL_API_KEY=your-deepl-api-key
OPENAI_API_KEY=your-openai-api-key
ELEVENLABS_API_KEY=your-elevenlabs-api-key
CONVERTAPI_SECRET=your-convertapi-secret
ANTHROPIC_API_KEY=your-anthropic-api-key
```

### 4. Configure Languages

Create `supported_languages.json`:

```json
{
  "source_languages": {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish"
  },
  "target_languages": {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish"
  }
}
```

## 🖥️ Usage

### Quick Start Script

Use the provided script to pull latest changes and start the application:

**Linux/Mac:**
```bash
./start_app.sh
```

**Windows:**
```batch
start_app.bat
```

The startup script will:
1. Pull latest changes from git
2. Detect and activate the virtual environment (venv or env)
3. Update dependencies from requirements.txt
4. Start the GUI application

### GUI Application

1. Launch the application: `python main.py`
2. Select the desired tool tab
3. Choose processing mode (single file or folder)
4. Select languages (for translation tools)
5. Choose input files and output directory
6. Click "Process" to start

### API Server

1. Start the server: `python api_server.py`
2. Access documentation at http://localhost:8000/docs
3. Use authentication token for API requests
4. Monitor task progress via task endpoints

## 📁 Project Structure

```
Language-Toolkit/
├── main.py                 # GUI application entry point
├── api_server.py          # FastAPI server
├── ui/                    # GUI components
│   ├── base_tool.py       # Base tool class
│   └── mixins.py          # Shared UI mixins
├── tools/                 # Tool implementations
│   ├── text_to_speech.py
│   ├── audio_transcription.py
│   ├── pptx_translation.py
│   └── ...
├── services/              # Business logic
│   ├── translation.py
│   ├── transcription.py
│   └── ...
├── utils/                 # Utility functions
├── docs/                  # Documentation
│   ├── api/              # API documentation
│   ├── deployment/       # Deployment guides
│   └── development/      # Development guides
└── tests/                # Test suite
```

## 📚 Documentation

- [API Reference](docs/api/README.md) - Complete API endpoint documentation
- [Authentication Guide](docs/api/authentication.md) - JWT authentication setup
- [Deployment Guide](docs/deployment/README.md) - Production deployment instructions
- [Docker Setup](docs/deployment/docker.md) - Container deployment
- [Development Guide](docs/development/README.md) - Contributing and development setup
- [Testing Guide](docs/development/testing.md) - Test suite documentation

## 🧪 Testing

```bash
# Run test suite
pytest tests/

# Run with coverage
pytest --cov=. tests/
```

## 🐳 Docker Support

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or use individual containers
docker build -t language-toolkit .
docker run -p 8000:8000 language-toolkit
```

## 🤝 Contributing

We welcome contributions! Please see our [Development Guide](docs/development/README.md) for details on:

- Setting up your development environment
- Code style guidelines
- Testing requirements
- Pull request process

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/Asi0Flammeus/Language-Toolkit/issues)
- **Documentation**: [Full Documentation](docs/README.md)
- **API Reference**: http://localhost:8000/docs (when running)

---

Made with ❤️ by asi0 and Claude agents

