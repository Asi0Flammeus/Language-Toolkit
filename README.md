
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

1. Start the application:
```bash
python main.py
```

2. Select the desired tool tab (PPTX Translation, Text Translation, or Audio Transcription)

3. Choose processing mode:
   - Single File: Process individual files
   - Folder (Recursive): Process all supported files in a directory and its subdirectories

4. Select source and target languages (for translation tools)

5. Choose input files/folder and output directory

6. Click "Process" to start the operation

## Supported File Types

- PPTX Translation: `.pptx`
- Text Translation: `.txt`
- Audio Transcription: `.wav`, `.mp3`, `.m4a`, `.webm`, `.mp4`, `.mpga`, `.mpeg`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
