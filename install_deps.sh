#!/bin/bash
# Install dependencies for Python 3.8 with compatibility handling

set -e

echo "Installing core dependencies..."

# Upgrade pip first
pip3 install --upgrade pip setuptools wheel

# Core API Framework
pip3 install fastapi==0.115.12
pip3 install "uvicorn[standard]==0.34.3"
pip3 install gunicorn==23.0.0
pip3 install python-multipart==0.0.20
pip3 install starlette==0.46.2

# Data Validation (Python 3.8 compatible)
pip3 install pydantic==2.10.6
pip3 install pydantic_core==2.27.2
pip3 install typing_extensions==4.13.0
pip3 install annotated-types==0.7.0

# HTTP Clients
pip3 install requests==2.32.3
pip3 install httpx==0.28.1
pip3 install urllib3==2.3.0
pip3 install certifi

# AI & Translation Services
echo "Installing AI and translation services..."
pip3 install deepl==1.21.1
pip3 install elevenlabs==1.56.0
pip3 install convertapi==2.0.0
pip3 install openai==1.70.0
pip3 install "anthropic>=0.64.0"

# Document Processing
echo "Installing document processing libraries..."
pip3 install python-pptx==1.0.2
pip3 install PyMuPDF==1.25.5
pip3 install pillow==11.2.1
pip3 install lxml==5.3.1

# Audio Processing
echo "Installing audio processing libraries..."
pip3 install pydub==0.25.1
pip3 install soundfile==0.12.1
pip3 install pyloudnorm==0.1.1

# Try librosa (may need system dependencies)
echo "Installing librosa (this may take a while)..."
pip3 install librosa==0.10.2.post1 || echo "Warning: librosa failed, continuing..."

# Utilities
echo "Installing utilities..."
pip3 install python-dotenv==1.1.1
pip3 install tqdm==4.67.1
pip3 install click==8.2.1
pip3 install PyYAML==6.0.2

# GUI Dependencies
echo "Installing GUI dependencies..."
pip3 install tkinterdnd2==0.4.3 || echo "Warning: tkinterdnd2 failed, continuing..."

# AWS (optional)
pip3 install boto3 botocore s3transfer || echo "Warning: AWS SDK failed, continuing..."

echo ""
echo "Installation complete!"
echo ""
echo "Testing imports..."
python3 -c "import tkinter; print('✓ tkinter OK')"
python3 -c "import deepl; print('✓ deepl OK')"
python3 -c "import elevenlabs; print('✓ elevenlabs OK')"
python3 -c "from pptx import Presentation; print('✓ python-pptx OK')"
python3 -c "from dotenv import load_dotenv; print('✓ python-dotenv OK')"

echo ""
echo "Testing SVP CLI..."
python3 svp_cli.py --list-languages
