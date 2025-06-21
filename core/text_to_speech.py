"""
Text-to-Speech Core Module

This module provides text-to-speech functionality using the ElevenLabs API.
It can convert text files into high-quality audio with various voice options and settings.

Usage Examples:
    GUI: Integrated with file browsers, voice selection dropdowns, and audio controls
    API: Used via REST endpoints for audio generation services
    CLI: Command-line text-to-speech conversion for automation

Features:
    - ElevenLabs API integration for realistic voice synthesis
    - Multiple voice options with different characteristics
    - Customizable voice settings (stability, similarity, style)
    - Support for multilingual voices
    - Progress callback support for user feedback
    - Automatic retry logic for network reliability
    - Voice auto-detection from filenames

Voice Settings:
    - Stability: Controls voice consistency (0.0-1.0)
    - Similarity Boost: Enhances voice similarity (0.0-1.0)
    - Style: Adjusts speaking style (0.0-1.0)
    - Speaker Boost: Improves voice clarity (boolean)

Supported Text Formats:
    - Plain text files (.txt)
    - UTF-8 encoding
    - Handles large text content efficiently
"""

import logging
import requests
import json
import re
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

logger = logging.getLogger(__name__)

class TextToSpeechCore:
    """
    Core text-to-speech functionality using ElevenLabs API.
    
    This class provides high-quality text-to-speech conversion with support
    for multiple voices, customizable settings, and robust error handling.
    It can process text files and generate realistic audio output.
    
    Key Features:
        - Realistic voice synthesis via ElevenLabs API
        - Multiple voice options and characteristics
        - Customizable voice settings and parameters
        - Multilingual voice support
        - Progress tracking with callback support
        - Network retry logic for reliability
        - Voice auto-detection capabilities
    
    Requirements:
        - ElevenLabs API key
        - requests library
        - Valid text input files
    
    Example Usage:
        tts = TextToSpeechCore(api_key="your-elevenlabs-key")
        
        # Get available voices
        voices = tts.get_voices()
        
        # Generate audio with custom settings
        success = tts.generate_audio(
            input_path=Path("text.txt"),
            output_path=Path("audio.mp3"),
            voice_id="voice_id_here",
            voice_settings={
                "stability": 0.7,
                "similarity_boost": 0.8,
                "style": 0.2,
                "use_speaker_boost": True
            }
        )
    """
    
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize text-to-speech core.
        
        Args:
            api_key: ElevenLabs API key
            progress_callback: Optional callback function for progress updates
        """
        self.api_key = api_key
        self.progress_callback = progress_callback or (lambda x: None)
        self.voices = []
        self._load_voices()
    
    def _load_voices(self):
        """Load available voices from ElevenLabs API."""
        if not self.api_key:
            logger.warning("ElevenLabs API key not provided")
            return
        
        try:
            url = "https://api.elevenlabs.io/v1/voices"
            headers = {"xi-api-key": self.api_key}
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            self.voices = data.get("voices", [])
            self.progress_callback(f"Loaded {len(self.voices)} voices")
            
        except Exception as e:
            logger.error(f"Failed to load voices: {e}")
            self.voices = []
    
    def generate_audio(self, input_path: Path, output_path: Path, 
                      voice_id: str, voice_settings: Optional[Dict[str, Any]] = None) -> bool:
        """
        Generate audio from text file.
        
        Args:
            input_path: Path to input text file
            output_path: Path to output audio file
            voice_id: ElevenLabs voice ID
            voice_settings: Optional voice settings (stability, similarity_boost, style, use_speaker_boost)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.progress_callback(f"Reading text file: {input_path}")
            
            # Read input text
            with open(input_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if not text.strip():
                raise ValueError("Input file is empty")
            
            # Generate audio
            audio_data = self._generate_audio_from_text(text, voice_id, voice_settings)
            
            # Save audio file
            self.progress_callback(f"Saving audio to: {output_path}")
            with open(output_path, 'wb') as f:
                f.write(audio_data)
            
            self.progress_callback("Audio generation completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to generate audio: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def _generate_audio_from_text(self, text: str, voice_id: str, 
                                 voice_settings: Optional[Dict[str, Any]] = None) -> bytes:
        """Generate audio from text using ElevenLabs API."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        # Default voice settings
        default_settings = {
            "stability": 0.5,
            "similarity_boost": 0.5,
            "style": 0.0,
            "use_speaker_boost": True
        }
        
        if voice_settings:
            default_settings.update(voice_settings)
        
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": default_settings
        }
        
        # Retry logic for network issues
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self.progress_callback(f"Generating audio (attempt {attempt}/{self.MAX_RETRIES})")
                
                response = requests.post(url, json=data, headers=headers)
                response.raise_for_status()
                
                return response.content
                
            except requests.exceptions.RequestException as e:
                if attempt == self.MAX_RETRIES:
                    raise RuntimeError(f"Failed to generate audio after {self.MAX_RETRIES} attempts: {e}")
                
                self.progress_callback(f"Network error: {e}. Retrying in {self.RETRY_DELAY} seconds...")
                time.sleep(self.RETRY_DELAY)
    
    def get_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voices."""
        return self.voices
    
    def find_voice_by_name(self, voice_name: str) -> Optional[str]:
        """Find voice ID by voice name."""
        for voice in self.voices:
            if voice.get("name", "").lower() == voice_name.lower():
                return voice.get("voice_id")
        return None
    
    def parse_voice_selection(self, voice_input: str) -> Optional[str]:
        """Parse voice selection from various input formats."""
        if not voice_input:
            return None
        
        voice_input = voice_input.strip()
        
        # Check if it's already a voice ID (format: voice_id)
        if re.match(r'^[a-zA-Z0-9]{20,}$', voice_input):
            return voice_input
        
        # Try to find by name
        voice_id = self.find_voice_by_name(voice_input)
        if voice_id:
            return voice_id
        
        # Try to extract from "Name (ID)" format
        match = re.search(r'\\(([a-zA-Z0-9]+)\\)$', voice_input)
        if match:
            return match.group(1)
        
        return None
    
    def validate_text_file(self, file_path: Path) -> bool:
        """Validate that the file is a readable text file."""
        if not file_path.exists():
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(100)  # Read first 100 characters
                return len(content.strip()) > 0
        except Exception:
            return False