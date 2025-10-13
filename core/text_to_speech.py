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
                      voice_id: str, voice_settings: Optional[Dict[str, Any]] = None) -> bool:
        """
        Generate audio from text file with normalization.

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

            text_length = len(text)
            logger.info(f"Processing text of {text_length} characters")

            # Generate audio
            audio_data = self._generate_audio_from_text(
                text, voice_id, voice_settings
            )

            # Save audio file
            self.progress_callback(f"Saving audio to: {output_path}")
            with open(output_path, 'wb') as f:
                f.write(audio_data)

            # Apply LUFS-based loudness normalization to all audio files
            self.normalize_audio(output_path, target_lufs=-14.0, tp_db=-1.0)

            self.progress_callback("Audio generation completed successfully")
            return True

        except Exception as e:
            error_msg = f"Failed to generate audio: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def _generate_audio_from_text(self, text: str, voice_id: str,
                                 voice_settings: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Generate audio from text using ElevenLabs API.

        Args:
            text: Text to convert to speech
            voice_id: ElevenLabs voice ID
            voice_settings: Optional voice settings

        Returns:
            Audio bytes
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

    def normalize_audio(self, audio_path: Path, target_lufs: float = -14.0, tp_db: float = -1.0) -> bool:
        """
        Apply comprehensive audio processing: compression, cleaning, and normalization.

        Uses FFmpeg filter chain:
        1. Dynamic compression - Reduces volume variations within audio
        2. High-pass filter - Removes low-frequency rumble (<80Hz)
        3. Noise reduction - FFT-based denoising for background noise
        4. De-clicking - Removes clicks and pops
        5. De-essing - Reduces harsh sibilance
        6. Loudnorm - EBU R128 / ITU-R BS.1770 loudness standards

        This ensures consistent voice levels throughout the file (prevents quieter voice over time),
        removes audio artifacts and background noise, and normalizes loudness across all files.

        Args:
            audio_path: Path to audio file to normalize
            target_lufs: Target integrated loudness in LUFS (default: -14.0)
            tp_db: True-peak ceiling in dBFS (default: -1.0)

        Returns:
            True if normalization was applied successfully, False otherwise
        """
        import subprocess

        # Temp output path
        temp_output = audio_path.with_suffix('.normalized.mp3')

        try:
            self.progress_callback(f"Applying compression, cleaning, and normalization (target: {target_lufs} LUFS)...")
            logger.info(f"Processing audio for {audio_path.name}: compression → cleaning → normalization (target: {target_lufs} LUFS, peak: {tp_db} dBFS)")

            # FFmpeg filter chain:
            # 1. acompressor: Reduces dynamic range to keep voice consistent
            #    - threshold=-20dB: Start compressing above -20dB
            #    - ratio=4: 4:1 compression ratio (moderate)
            #    - attack=5ms, release=50ms: Fast response for speech
            #    - makeup=2dB: Slight gain boost after compression
            # 2. highpass: Remove low-frequency rumble below 80Hz
            # 3. afftdn: FFT-based noise reduction
            #    - nf=-25: Noise floor in dB (moderate noise reduction)
            # 4. adeclick: Remove clicks and pops
            #    - t=2: Detection threshold (clicks)
            #    - w=20: Window size for detection
            # 5. deesser: Reduce harsh sibilance (s/sh sounds)
            #    - i=0.1: Intensity (mild de-essing)
            #    - f=0.5: Normalized frequency (0-1 range, 0.5 = Nyquist/2 ≈ 5.5kHz at 44.1kHz)
            # 6. loudnorm: EBU R128 loudness normalization
            #    - I=target_lufs: Integrated loudness target
            #    - TP=tp_db: True-peak ceiling
            #    - LRA=11: Loudness range target (standard for speech)
            filter_complex = (
                f"acompressor=threshold=-20dB:ratio=4:attack=5:release=50:makeup=2dB,"
                f"highpass=f=80,"
                f"afftdn=nf=-25,"
                f"adeclick=t=2:w=20,"
                f"deesser=i=0.1:f=0.5,"
                f"loudnorm=I={target_lufs}:TP={tp_db}:LRA=11"
            )

            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output
                '-i', str(audio_path),
                '-af', filter_complex,
                '-codec:a', 'libmp3lame',
                '-b:a', '320k',
                str(temp_output)
            ]

            logger.debug(f"Running FFmpeg command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )

            # Replace original with normalized version
            temp_output.replace(audio_path)

            self.progress_callback("Audio processing complete: compression, cleaning, and normalization applied")
            logger.info(f"Successfully processed {audio_path.name}: compression → noise reduction → de-clicking → de-essing → loudnorm")
            return True

        except subprocess.CalledProcessError as e:
            logger.warning(f"Normalization failed for {audio_path.name}: {e.stderr}")
            self.progress_callback(f"Warning: Normalization failed - {e.stderr}")
            # Clean up temp file if it exists
            if temp_output.exists():
                temp_output.unlink()
            return False
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
                            voice_settings: Optional[Dict[str, Any]] = None) -> bool:
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
