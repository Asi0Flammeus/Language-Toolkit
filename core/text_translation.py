"""
Text Translation Core Module

This module provides text file translation functionality using multiple translation providers
configured in language_provider.json (DeepL, Google Translate, OpenAI).

It automatically selects the appropriate provider based on the target language and routes
requests through the ConfigBasedTranslator.

Usage Examples:
    GUI: Integrated with file browsers, language selection, and progress indicators
    API: Used via REST endpoints for text translation services
    CLI: Command-line text translation for batch processing

Features:
    - Multi-provider support (DeepL, Google, OpenAI) via configuration
    - Automatic provider selection based on language_provider.json
    - Support for plain text file translation
    - Direct string translation capability
    - Language auto-detection support
    - Progress callback support for user feedback
    - Comprehensive error handling and validation
    - Support for all configured language pairs

Supported Text Formats:
    - Plain text files (.txt)
    - UTF-8 encoding support
    - Preserves line breaks and basic formatting
    - Handles large text files efficiently

Provider Selection:
    Provider is automatically selected based on target language from language_provider.json:
    - Czech, German, most European languages → DeepL
    - Hindi, Rundi, Swahili, Vietnamese → Google Translate
    - Farsi, Sinhala, Serbian Latin, Thai → OpenAI
"""

import logging
import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from .text_translation_config import ConfigBasedTranslator

logger = logging.getLogger(__name__)


class TextTranslationCore:
    """
    Core text translation functionality using multiple providers via configuration.

    This class provides high-quality text translation capabilities using the best
    provider for each language pair as defined in language_provider.json.

    Key Features:
        - Multi-provider support (DeepL, Google, OpenAI)
        - Automatic provider selection per language
        - File and string translation support
        - Automatic language detection
        - Progress tracking with callback support
        - UTF-8 encoding support
        - Comprehensive error handling

    Requirements:
        - At least one provider API key (via constructor or environment)
        - language_provider.json configuration file
        - Valid text input files or strings

    Example Usage:
        # Initialize with environment variables (recommended)
        translator = TextTranslationCore()

        # Or pass keys explicitly
        translator = TextTranslationCore(
            deepl_api_key="your-deepl-key",
            google_api_key="your-google-key",
            openai_api_key="your-openai-key"
        )

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

    def __init__(self,
                 api_key: Optional[str] = None,
                 deepl_api_key: Optional[str] = None,
                 google_api_key: Optional[str] = None,
                 openai_api_key: Optional[str] = None,
                 progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize text translation core.

        Args:
            api_key: Backward compatibility - will try to detect provider
            deepl_api_key: DeepL API key (or use DEEPL_API_KEY env var)
            google_api_key: Google API key (or use GOOGLE_API_KEY env var)
            openai_api_key: OpenAI API key (or use OPENAI_API_KEY env var)
            progress_callback: Optional callback function for progress updates

        Note:
            If no keys are provided, will attempt to load from environment variables:
            - DEEPL_API_KEY
            - GOOGLE_API_KEY
            - OPENAI_API_KEY
        """
        self.progress_callback = progress_callback or (lambda x: None)

        # Handle backward compatibility with single api_key parameter
        if api_key and not any([deepl_api_key, google_api_key, openai_api_key]):
            # Try to detect which provider the key is for
            if ':fx' in api_key or api_key.startswith('DeepL-Auth-Key'):
                deepl_api_key = api_key
            elif api_key.startswith('sk-'):
                openai_api_key = api_key
            elif api_key.startswith('AIza'):
                google_api_key = api_key
            else:
                # Default fallback: try as DeepL first
                deepl_api_key = api_key

        # Initialize the configuration-based translator
        try:
            self.translator = ConfigBasedTranslator(
                deepl_api_key=deepl_api_key,
                google_api_key=google_api_key,
                openai_api_key=openai_api_key,
                progress_callback=self.progress_callback
            )
            self.progress_callback("Translation system initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize translator: {e}")

    def translate_text_file(self, input_path: Path, output_path: Path,
                           source_lang: str, target_lang: str) -> bool:
        """
        Translate text file from source to target language.

        Automatically selects the best provider based on target language
        from language_provider.json configuration.

        Args:
            input_path: Path to input text file
            output_path: Path to output text file
            source_lang: Source language code (e.g., 'en' or 'auto')
            target_lang: Target language code (e.g., 'fr', 'zh-Hans')

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
            self.progress_callback(f"Translating text: {source_lang} → {target_lang}")
            translated_text = self.translate_text(text, source_lang, target_lang)

            # Save translated text
            self.progress_callback(f"Saving translation to: {output_path}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
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
        Translate text string using the appropriate provider.

        Args:
            text: Text to translate
            source_lang: Source language code (or 'auto' for detection)
            target_lang: Target language code

        Returns:
            Translated text

        Raises:
            ValueError: If language is not supported
            RuntimeError: If translation fails
        """
        if not text.strip():
            return text

        try:
            return self.translator.translate_text(text, source_lang, target_lang)
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            raise

    def validate_text_file(self, file_path: Path) -> bool:
        """
        Validate that the file is a readable text file.

        Args:
            file_path: Path to file to validate

        Returns:
            True if file is readable as text, False otherwise
        """
        if not file_path.exists():
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Try to read first few characters
                f.read(100)
            return True
        except Exception:
            return False

    def get_supported_languages(self) -> Dict[str, Any]:
        """
        Get languages supported by all configured providers.

        Returns:
            Dictionary with 'all' and 'by_provider' keys containing
            language information from language_provider.json
        """
        try:
            return self.translator.get_supported_languages()
        except Exception as e:
            logger.error(f"Failed to get supported languages: {e}")
            return {"all": [], "by_provider": {}}

    def get_available_providers(self) -> list:
        """
        Get list of initialized and available providers.

        Returns:
            List of provider names (e.g., ['deepl', 'google', 'openai'])
        """
        try:
            return self.translator.get_available_providers()
        except Exception as e:
            logger.error(f"Failed to get available providers: {e}")
            return []

    def validate_language_pair(self, source_lang: str, target_lang: str) -> tuple:
        """
        Validate if a language pair is supported.

        Args:
            source_lang: Source language code
            target_lang: Target language code

        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        try:
            return self.translator.validate_language_pair(source_lang, target_lang)
        except Exception as e:
            return False, f"Validation error: {e}"
