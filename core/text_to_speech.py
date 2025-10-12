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
from typing import Any, Callable, Dict, List, Optional, Tuple

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
        self.voice_mapping = {}  # Will be populated from API
        
        # Load available voices from API
        self._load_voices_from_api()
    
    def _load_voices_from_api(self):
        """Load available voices from ElevenLabs API."""
        if not self.api_key:
            logger.warning("ElevenLabs API key not provided")
            return
        
        try:
            url = "https://api.elevenlabs.io/v1/voices"
            headers = {"xi-api-key": self.api_key}
            
            self.progress_callback("Fetching voices from ElevenLabs API...")
            response = requests.get(url, headers=headers, params={"show_legacy": "false"})
            response.raise_for_status()
            
            data = response.json()
            self.voices = data.get("voices", [])
            
            # Build voice mapping from API data
            self.voice_mapping = {}
            for voice in self.voices:
                name = voice.get("name", "")
                voice_id = voice.get("voice_id", "")
                if name and voice_id:
                    self.voice_mapping[name] = voice_id
            
            self.progress_callback(f"Loaded {len(self.voices)} voices from API")
            
        except Exception as e:
            logger.error(f"Failed to load voices: {e}")
            self.voices = []
    
    def generate_audio(self, input_path: Path, output_path: Path,
                      voice_id: str, voice_settings: Optional[Dict[str, Any]] = None,
                      previous_request_ids: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
        """
        Generate audio from text file with optional request stitching and normalization.

        Args:
            input_path: Path to input text file
            output_path: Path to output audio file
            voice_id: ElevenLabs voice ID
            voice_settings: Optional voice settings (stability, similarity_boost, style, use_speaker_boost)
            previous_request_ids: Optional list of previous request IDs for stitching

        Returns:
            Tuple of (success, request_id)
        """
        try:
            self.progress_callback(f"Reading text file: {input_path}")

            # Read input text
            with open(input_path, 'r', encoding='utf-8') as f:
                text = f.read()

            if not text.strip():
                raise ValueError("Input file is empty")

            text_length = len(text)
            logger.info(f"Processing text of {text_length} characters")

            # Generate audio with optional request stitching
            audio_data, request_id = self._generate_audio_from_text(
                text, voice_id, voice_settings, previous_request_ids
            )

            # Save audio file
            self.progress_callback(f"Saving audio to: {output_path}")
            with open(output_path, 'wb') as f:
                f.write(audio_data)

            # Apply normalization for texts >800 chars (conservative)
            self.normalize_audio(output_path, text_length, threshold=800)

            self.progress_callback("Audio generation completed successfully")
            return True, request_id

        except Exception as e:
            error_msg = f"Failed to generate audio: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False, None
    
    def _generate_audio_from_text(self, text: str, voice_id: str,
                                 voice_settings: Optional[Dict[str, Any]] = None,
                                 previous_request_ids: Optional[List[str]] = None) -> Tuple[bytes, Optional[str]]:
        """
        Generate audio from text using ElevenLabs API with optional request stitching.

        Args:
            text: Text to convert to speech
            voice_id: ElevenLabs voice ID
            voice_settings: Optional voice settings
            previous_request_ids: Optional list of previous request IDs for stitching (max 3)

        Returns:
            Tuple of (audio_bytes, request_id)
        """
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

        # Add request stitching if previous request IDs provided
        if previous_request_ids:
            # Limit to max 3 IDs as per ElevenLabs API
            data["previous_request_ids"] = previous_request_ids[-3:]
            logger.info(f"Using request stitching with {len(data['previous_request_ids'])} previous ID(s)")

        # Retry logic for network issues
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self.progress_callback(f"Generating audio (attempt {attempt}/{self.MAX_RETRIES})")

                response = requests.post(url, json=data, headers=headers)
                response.raise_for_status()

                # Capture request ID for stitching chain
                request_id = response.headers.get('request-id')
                if request_id:
                    logger.debug(f"Captured request ID: {request_id}")

                return response.content, request_id

            except requests.exceptions.RequestException as e:
                if attempt == self.MAX_RETRIES:
                    raise RuntimeError(f"Failed to generate audio after {self.MAX_RETRIES} attempts: {e}")

                self.progress_callback(f"Network error: {e}. Retrying in {self.RETRY_DELAY} seconds...")
                time.sleep(self.RETRY_DELAY)

    def normalize_audio(self, audio_path: Path, text_length: int, threshold: int = 800) -> bool:
        """
        Apply volume normalization for texts exceeding threshold (conservative approach).

        Args:
            audio_path: Path to audio file to normalize
            text_length: Length of original text in characters
            threshold: Character threshold for applying normalization (default: 800)

        Returns:
            True if normalization was applied, False otherwise
        """
        if text_length <= threshold:
            logger.debug(f"Skipping normalization (text length: {text_length} <= {threshold})")
            return False

        try:
            from pydub import AudioSegment
            from pydub.effects import normalize

            self.progress_callback(f"Applying volume normalization (text: {text_length} chars, threshold: {threshold})...")
            logger.info(f"Normalizing audio for {audio_path.name} (text length: {text_length})")

            # Load audio
            audio = AudioSegment.from_mp3(audio_path)

            # Apply normalization with 3dB headroom
            normalized = normalize(audio, headroom=3.0)

            # Export back to same file
            normalized.export(audio_path, format="mp3", bitrate="128k")

            self.progress_callback("Volume normalization applied successfully")
            logger.info(f"Successfully normalized {audio_path.name}")
            return True

        except Exception as e:
            logger.warning(f"Normalization failed for {audio_path.name}: {e}")
            self.progress_callback(f"Warning: Normalization failed - {e}")
            return False

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
        1. Direct voice ID format
        2. API voice name lookup (exact match)
        3. API voice name lookup (case-insensitive)
        4. "Name (ID)" format extraction
        """
        if not voice_input:
            return None
        
        voice_input = voice_input.strip()
        
        # 1. Check if it's already a voice ID (format: alphanumeric string)
        if re.match(r'^[a-zA-Z0-9]{20,}$', voice_input):
            return voice_input
        
        # 2. Try exact match in API voices
        if voice_input in self.voice_mapping:
            voice_id = self.voice_mapping[voice_input]
            logger.debug(f"Found voice '{voice_input}' in API mapping: {voice_id}")
            return voice_id
        
        # 3. Try case-insensitive match in API voices
        for voice_name, voice_id in self.voice_mapping.items():
            if voice_name.lower() == voice_input.lower():
                logger.debug(f"Found voice '{voice_name}' (case-insensitive) in API mapping: {voice_id}")
                return voice_id
        
        # 4. Try to extract from "Name (ID)" format
        match = re.search(r'\(([a-zA-Z0-9]+)\)$', voice_input)
        if match:
            return match.group(1)
        
        logger.warning(f"Could not resolve voice: '{voice_input}'. Available API voices: {list(self.voice_mapping.keys())}")
        return None
    
    def get_available_voice_names(self) -> Dict[str, str]:
        """
        Get all available voice names and their IDs from API.
        
        Returns:
            Dictionary mapping voice names to voice IDs
        """
        return self.voice_mapping.copy()
    
    def extract_voice_from_filename(self, file_path: Path) -> Optional[str]:
        """
        Extract voice name from filename by matching against known API voice names.
        
        For file 'test_Rachel_transcript_en.txt':
        - Splits into parts: ['test', 'Rachel', 'transcript', 'en']  
        - Checks each part against API voice names
        - Returns 'Rachel' if found in the API voices
        
        Args:
            file_path: Path to the input file
            
        Returns:
            Voice name if found in API voices, None otherwise
        """
        # Split filename by underscores, hyphens, spaces, and dots
        filename_parts = re.split(r'[_\-\s\.]+', file_path.stem)
        
        # Check each part against API voice mapping (case-insensitive)
        for part in filename_parts:
            part_clean = part.strip()
            
            # Direct match (case-sensitive)
            if part_clean in self.voice_mapping:
                logger.info(f"Found voice '{part_clean}' in filename '{file_path.name}'")
                return part_clean
            
            # Case-insensitive match
            for voice_name in self.voice_mapping.keys():
                if part_clean.lower() == voice_name.lower():
                    logger.info(f"Found voice '{voice_name}' (case-insensitive) in filename '{file_path.name}'")
                    return voice_name
        
        logger.debug(f"No voice found in filename '{file_path.name}'. Available API voices: {list(self.voice_mapping.keys())[:10]}...")
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
    
    def text_to_speech_file(self, input_path: Path, output_path: Path,
                            voice_settings: Optional[Dict[str, Any]] = None,
                            previous_request_ids: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
        """
        Convert a text file to speech audio with intelligent voice detection and request stitching.

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
            previous_request_ids: Optional list of previous request IDs for stitching

        Returns:
            Tuple of (success, request_id)
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
            return False, None

        return self.generate_audio(input_path, output_path, voice_id, voice_settings, previous_request_ids)