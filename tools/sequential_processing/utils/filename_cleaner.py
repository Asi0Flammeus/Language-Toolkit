"""Filename cleaning utilities for sequential processing."""

import re
import logging
import os
from pathlib import Path
from typing import Set, Optional
import requests

logger = logging.getLogger(__name__)


class FilenameCleanerUtility:
    """Utility class for cleaning filenames by removing voice names."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize filename cleaner with ElevenLabs API key.

        Args:
            api_key: ElevenLabs API key for fetching voice names
        """
        self.api_key = api_key or os.getenv('ELEVENLABS_API_KEY')
        self.voice_names = set()
        self._load_voice_names()

    def _load_voice_names(self) -> None:
        """Load voice names from ElevenLabs API."""
        if not self.api_key:
            logger.warning("No ElevenLabs API key provided, using fallback voice names")
            self._load_fallback_voice_names()
            return

        try:
            url = "https://api.elevenlabs.io/v1/voices"
            headers = {"xi-api-key": self.api_key}

            response = requests.get(url, headers=headers, params={"show_legacy": "false"})
            response.raise_for_status()

            data = response.json()
            voices = data.get("voices", [])

            # Extract all voice names
            for voice in voices:
                name = voice.get("name", "").strip()
                if name:
                    self.voice_names.add(name)
                    # Also add lowercase version for case-insensitive matching
                    self.voice_names.add(name.lower())

            logger.info(f"Loaded {len(voices)} voice names from ElevenLabs API")

        except Exception as e:
            logger.error(f"Failed to load voice names from API: {e}")
            # Fallback to common voice names if API fails
            self._load_fallback_voice_names()

    def _load_fallback_voice_names(self) -> None:
        """Load fallback voice names if API is unavailable."""
        # Common ElevenLabs voice names as fallback
        fallback_names = [
            "Rachel", "Domi", "Bella", "Antoni", "Elli", "Josh", "Arnold",
            "Adam", "Sam", "Dorothy", "Nicole", "Charlotte", "Emily", "Matilda",
            "Matthew", "James", "Joseph", "Harry", "Ethan", "Chris", "Gigi",
            "Freya", "Brian", "Grace", "Daniel", "Lily", "Charlie", "George",
            "Callum", "Patrick", "Fin", "Sarah", "Laura", "Bill", "Jessica",
            "Eric", "Liam", "Thomas", "Drew", "Paul", "Jessie", "Clyde",
            "Dave", "Serena", "Michael", "Aria", "Roger", "Alice", "Valentino",
            "Fanis", "Loic", "Rogzy", "Santa", "Amy", "Emma", "Anna", "Jenny",
            "Will"
        ]

        for name in fallback_names:
            self.voice_names.add(name)
            self.voice_names.add(name.lower())

        logger.info(f"Loaded {len(fallback_names)} fallback voice names")

    def remove_voice_from_filename(self, filename: str) -> str:
        """
        Remove voice names from a filename.

        This method searches for voice names in the filename and removes them,
        cleaning up any resulting duplicate separators.

        Args:
            filename: The filename to clean (with or without extension)

        Returns:
            Cleaned filename with voice names removed
        """
        if not self.voice_names:
            return filename

        # Split filename and extension
        path = Path(filename)
        name_without_ext = path.stem
        extension = path.suffix

        # Original name for comparison
        original_name = name_without_ext

        # Check each voice name
        for voice_name in self.voice_names:
            # Create patterns to match the voice name with separators
            patterns = [
                # Voice name surrounded by underscores or hyphens
                rf'[_\-]{re.escape(voice_name)}[_\-]',
                # Voice name at the start followed by separator
                rf'^{re.escape(voice_name)}[_\-]',
                # Voice name at the end preceded by separator
                rf'[_\-]{re.escape(voice_name)}$',
                # Voice name as a standalone word (case-insensitive)
                rf'\b{re.escape(voice_name)}\b',
            ]

            for pattern in patterns:
                # Case-insensitive replacement
                name_without_ext = re.sub(pattern, '_', name_without_ext, flags=re.IGNORECASE)

        # Clean up multiple underscores/hyphens
        name_without_ext = re.sub(r'[_\-]{2,}', '_', name_without_ext)
        # Clean up leading/trailing underscores/hyphens
        name_without_ext = name_without_ext.strip('_-')

        # If the name becomes empty, use a default
        if not name_without_ext:
            name_without_ext = "output"

        # Log if changes were made
        if name_without_ext != original_name:
            logger.debug(f"Cleaned filename: '{original_name}' -> '{name_without_ext}'")

        # Return with extension
        return f"{name_without_ext}{extension}"

    def clean_path(self, file_path: Path) -> Path:
        """
        Clean a file path by removing voice names from the filename.

        Args:
            file_path: Path object to clean

        Returns:
            New Path object with cleaned filename
        """
        cleaned_name = self.remove_voice_from_filename(file_path.name)
        return file_path.parent / cleaned_name