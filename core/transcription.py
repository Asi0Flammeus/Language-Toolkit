"""Audio Transcription Core Functionality"""

import logging
import openai
from pathlib import Path
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)

class AudioTranscriptionCore:
    """Core audio transcription functionality without GUI dependencies."""
    
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