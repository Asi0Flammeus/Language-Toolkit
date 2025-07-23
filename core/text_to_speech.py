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

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests

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
        self.local_voice_mapping = {}
        
        # Load local voice mapping from elevenlabs_voices.json
        self._load_local_voice_mapping()
        
        # Load available voices from API
        self._load_voices()
    
    def _load_local_voice_mapping(self):
        """Load local voice name to ID mapping from elevenlabs_voices.json."""
        try:
            # Look for the file in the project root directory
            voices_file = Path(__file__).parent.parent / "elevenlabs_voices.json"
            
            if voices_file.exists():
                with open(voices_file, 'r', encoding='utf-8') as f:
                    self.local_voice_mapping = json.load(f)
                    logger.info(f"Loaded {len(self.local_voice_mapping)} local voice mappings from {voices_file}")
            else:
                logger.warning(f"Local voice mapping file not found: {voices_file}")
                
        except Exception as e:
            logger.error(f"Failed to load local voice mapping: {e}")
            self.local_voice_mapping = {}
    
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
        """
        Parse voice selection from various input formats.
        
        Priority order:
        1. Local voice mapping from elevenlabs_voices.json  
        2. Direct voice ID format
        3. API voice name lookup
        4. "Name (ID)" format extraction
        """
        if not voice_input:
            return None
        
        voice_input = voice_input.strip()
        
        # 1. Check local voice mapping first (highest priority)
        if voice_input in self.local_voice_mapping:
            voice_id = self.local_voice_mapping[voice_input]
            logger.debug(f"Found voice '{voice_input}' in local mapping: {voice_id}")
            return voice_id
        
        # 2. Check if it's already a voice ID (format: voice_id)
        if re.match(r'^[a-zA-Z0-9]{20,}$', voice_input):
            return voice_input
        
        # 3. Try to find by name in API voices
        voice_id = self.find_voice_by_name(voice_input)
        if voice_id:
            return voice_id
        
        # 4. Try to extract from "Name (ID)" format
        match = re.search(r'\\(([a-zA-Z0-9]+)\\)$', voice_input)
        if match:
            return match.group(1)
        
        logger.warning(f"Could not resolve voice: '{voice_input}'. Available local voices: {list(self.local_voice_mapping.keys())}")
        return None
    
    def get_available_voice_names(self) -> Dict[str, str]:
        """
        Get all available voice names and their IDs.
        
        Returns:
            Dictionary mapping voice names to voice IDs, with local mappings taking priority
        """
        # Start with API voices
        voice_map = {}
        for voice in self.voices:
            name = voice.get("name", "")
            voice_id = voice.get("voice_id", "")
            if name and voice_id:
                voice_map[name] = voice_id
        
        # Override with local mappings (they take priority)
        voice_map.update(self.local_voice_mapping)
        
        return voice_map
    
    def extract_voice_from_filename(self, file_path: Path) -> Optional[str]:
        """
        Extract voice name from filename by matching against known voice names.
        
        For file 'test_Loic_transcript_fr.txt':
        - Splits into parts: ['test', 'Loic', 'transcript', 'fr']  
        - Checks each part against elevenlabs_voices.json keys
        - Returns 'Loic' if found in the mapping
        
        Args:
            file_path: Path to the input file
            
        Returns:
            Voice name if found in local mapping, None otherwise
        """
        # Split filename by underscores, hyphens, and spaces
        filename_parts = re.split(r'[_\-\s]+', file_path.stem)
        
        # Check each part against local voice mapping (case-insensitive)
        for part in filename_parts:
            part_clean = part.strip()
            
            # Direct match (case-sensitive)
            if part_clean in self.local_voice_mapping:
                logger.debug(f"Found voice '{part_clean}' in filename '{file_path.name}'")
                return part_clean
            
            # Case-insensitive match
            for voice_name in self.local_voice_mapping.keys():
                if part_clean.lower() == voice_name.lower():
                    logger.debug(f"Found voice '{voice_name}' (case-insensitive) in filename '{file_path.name}'")
                    return voice_name
        
        logger.debug(f"No voice found in filename '{file_path.name}'. Available voices: {list(self.local_voice_mapping.keys())}")
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
    
    def text_to_speech_file(self, input_path: Path, output_path: Path, voice_settings: Optional[Dict[str, Any]] = None) -> bool:
        """
        Convert a text file to speech audio with intelligent voice detection.
        
        This method extracts voice names from filenames by matching against the 
        local voice mapping in elevenlabs_voices.json. It supports multiple 
        separators (underscore, hyphen, space) and case-insensitive matching.
        
        Examples:
            'test_Loic_transcript_fr.txt' → finds 'Loic' → uses voice ID from JSON
            'story-Fanis-english.txt' → finds 'Fanis' → uses voice ID from JSON  
            'content_Rogzy.txt' → finds 'Rogzy' → uses voice ID from JSON
            
        Fallback behavior:
            1. If no voice found in filename → uses first available API voice
            2. If no API voices available → returns False
            
        Args:
            input_path: Path to text file to convert
            output_path: Path where audio file will be saved
            voice_settings: Optional voice configuration overrides
            
        Returns:
            True if successful, False otherwise
        """
        # Extract voice name from filename using intelligent matching against local voice mapping
        voice_label = self.extract_voice_from_filename(input_path)
        
        # Convert the label to a voice_id using the existing helper
        voice_id = self.parse_voice_selection(voice_label or "") if voice_label else None

        # Fallback to first available voice when detection fails
        if not voice_id and self.voices:
            voice_id = self.voices[0].get("voice_id")

        if not voice_id:
            self.progress_callback("Error: Unable to determine voice ID for text-to-speech")
            logger.error("Unable to determine voice ID for TTS conversion of %s", input_path)
            return False

        return self.generate_audio(input_path, output_path, voice_id, voice_settings)