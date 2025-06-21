"""
Text Translation Core Module

This module provides text file translation functionality using the DeepL API.
It can translate plain text files between multiple languages while preserving formatting.

Usage Examples:
    GUI: Integrated with file browsers, language selection, and progress indicators
    API: Used via REST endpoints for text translation services
    CLI: Command-line text translation for batch processing

Features:
    - DeepL API integration for high-quality translation
    - Support for plain text file translation
    - Direct string translation capability
    - Language auto-detection support
    - Progress callback support for user feedback
    - Comprehensive error handling and validation
    - Support for all DeepL supported language pairs

Supported Text Formats:
    - Plain text files (.txt)
    - UTF-8 encoding support
    - Preserves line breaks and basic formatting
    - Handles large text files efficiently
"""

import logging
import deepl
from pathlib import Path
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)

class TextTranslationCore:
    """
    Core text translation functionality using DeepL API.
    
    This class provides high-quality text translation capabilities for both
    files and direct string translation. It supports automatic language
    detection and manual language specification.
    
    Key Features:
        - High-quality translation via DeepL API
        - File and string translation support
        - Automatic language detection
        - Manual source language specification
        - Progress tracking with callback support
        - UTF-8 encoding support
        - Comprehensive error handling
    
    Requirements:
        - DeepL API key
        - deepl Python library
        - Valid text input files or strings
    
    Example Usage:
        translator = TextTranslationCore(api_key="your-deepl-key")
        
        # File translation
        success = translator.translate_text_file(
            input_path=Path("document.txt"),
            output_path=Path("translated.txt"),
            source_lang="en",
            target_lang="fr"
        )
        
        # Direct string translation
        result = translator.translate_text("Hello world", "en", "fr")
    """
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize text translation core.
        
        Args:
            api_key: DeepL API key
            progress_callback: Optional callback function for progress updates
        """
        self.api_key = api_key
        self.progress_callback = progress_callback or (lambda x: None)
        self.translator = None
        self._init_translator()
    
    def _init_translator(self):
        """Initialize DeepL translator."""
        if not self.api_key:
            raise ValueError("DeepL API key is required")
        
        try:
            self.translator = deepl.Translator(self.api_key)
            self.progress_callback("DeepL translator initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize DeepL translator: {e}")
    
    def translate_text_file(self, input_path: Path, output_path: Path, 
                           source_lang: str, target_lang: str) -> bool:
        """
        Translate text file from source to target language.
        
        Args:
            input_path: Path to input text file
            output_path: Path to output text file
            source_lang: Source language code (e.g., 'en')
            target_lang: Target language code (e.g., 'fr')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.progress_callback(f"Reading text file: {input_path}")
            
            # Read input file
            with open(input_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if not text.strip():
                raise ValueError("Input file is empty")
            
            # Translate text
            self.progress_callback("Translating text...")
            translated_text = self.translate_text(text, source_lang, target_lang)
            
            # Save translated text
            self.progress_callback(f"Saving translation to: {output_path}")
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translated_text)
            
            self.progress_callback("Text translation completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to translate text file: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate text string.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translated text
        """
        if not text.strip():
            return text
        
        try:
            result = self.translator.translate_text(
                text,
                source_lang=source_lang if source_lang != 'auto' else None,
                target_lang=target_lang
            )
            return result.text
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            raise
    
    def validate_text_file(self, file_path: Path) -> bool:
        """Validate that the file is a readable text file."""
        if not file_path.exists():
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Try to read first few characters
                f.read(100)
            return True
        except Exception:
            return False
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get languages supported by DeepL."""
        try:
            if not self.translator:
                return {}
            
            source_langs = self.translator.get_source_languages()
            target_langs = self.translator.get_target_languages()
            
            supported = {}
            for lang in source_langs:
                supported[lang.code.lower()] = lang.name
            
            return supported
        except Exception as e:
            logger.error(f"Failed to get supported languages: {e}")
            return {}