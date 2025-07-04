"""
Audio Transcription Core Module

This module provides audio-to-text transcription functionality using OpenAI's Whisper API.
It can convert spoken audio in various formats into accurate text transcriptions.

Usage Examples:
    GUI: Integrated with file browsers, progress bars, and language selection dropdowns
    API: Used via REST endpoints for transcription services and batch processing
    CLI: Command-line audio transcription for automation workflows

Features:
    - OpenAI Whisper API integration for state-of-the-art transcription
    - Support for multiple audio formats (MP3, WAV, M4A, OGG, FLAC, WebM)
    - Language detection and manual language specification
    - Progress callback support for user feedback
    - Robust error handling and validation
    - High accuracy transcription results

Supported Audio Formats:
    - MP3 (most common)
    - WAV (uncompressed)
    - M4A (Apple format)
    - OGG (open source)
    - FLAC (lossless)
    - WebM (web format)
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import openai

logger = logging.getLogger(__name__)

class AudioTranscriptionCore:
    """
    Core audio transcription functionality using OpenAI Whisper API.
    
    This class provides high-quality audio-to-text transcription capabilities
    supporting multiple audio formats and languages. It uses OpenAI's Whisper
    model for accurate speech recognition.
    
    Key Features:
        - State-of-the-art transcription via OpenAI Whisper
        - Multi-format audio support
        - Automatic language detection
        - Manual language specification support
        - Progress tracking with callback support
        - Comprehensive error handling
        - High accuracy results
    
    Requirements:
        - OpenAI API key
        - openai Python library
        - Valid audio input files
    
    Example Usage:
        transcriber = AudioTranscriptionCore(api_key="your-openai-key")
        success = transcriber.transcribe_audio(
            input_path=Path("audio.mp3"),
            output_path=Path("transcript.txt"),
            language="en"  # Optional
        )
    """
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize audio transcription core.
        
        Args:
            api_key: OpenAI API key
            progress_callback: Optional callback function for progress updates
        """
        self.api_key = api_key
        self.progress_callback = progress_callback or (lambda x: None)
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize OpenAI client."""
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        try:
            self.client = openai.OpenAI(api_key=self.api_key)
            self.progress_callback("OpenAI client initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI client: {e}")
    
    def transcribe_audio(self, input_path: Path, output_path: Path, 
                        language: Optional[str] = None) -> bool:
        """
        Transcribe audio file to text.
        
        Args:
            input_path: Path to input audio file
            output_path: Path to output text file
            language: Optional language code for transcription
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.progress_callback(f"Starting transcription of: {input_path}")
            
            # Validate input file
            if not self.validate_audio_file(input_path):
                raise ValueError(f"Invalid audio file: {input_path}")
            
            # Transcribe audio
            with open(input_path, 'rb') as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language
                )
            
            # Save transcription
            self.progress_callback(f"Saving transcription to: {output_path}")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(transcript.text)
            
            self.progress_callback("Audio transcription completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to transcribe audio: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def validate_audio_file(self, file_path: Path) -> bool:
        """Validate that the file is a supported audio format."""
        if not file_path.exists():
            return False
        
        supported_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm'}
        return file_path.suffix.lower() in supported_extensions
    
    def get_supported_formats(self) -> list:
        """Get list of supported audio formats."""
        return ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm']

    def transcribe_audio_file(self, input_path: Path, output_path: Path, language: Optional[str] = None) -> bool:
        """Backward-compatibility wrapper.

        api_server.py historically expected a ``transcribe_audio_file`` method.  The
        core implementation was later renamed to :py:meth:`transcribe_audio`.  To
        avoid breaking the public API we provide this thin wrapper that simply
        delegates to the new name.
        """
        return self.transcribe_audio(input_path, output_path, language)