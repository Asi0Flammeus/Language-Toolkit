"""
Multi-Provider Text Translation Core Module

This module provides text file translation functionality using multiple translation providers:
- DeepL API for high-quality European language translation
- Google Translate for broader language support
- OpenAI GPT for context-aware and specialized translations

Usage Examples:
    GUI: Integrated with file browsers, language selection, and progress indicators
    API: Used via REST endpoints for text translation services
    CLI: Command-line text translation for batch processing

Features:
    - Multiple translation provider support (DeepL, Google, OpenAI)
    - Automatic provider selection based on language pair
    - Support for plain text file translation
    - Direct string translation capability
    - Language auto-detection support
    - Progress callback support for user feedback
    - Comprehensive error handling and validation
    - Support for all provider-specific language pairs

Supported Text Formats:
    - Plain text files (.txt)
    - UTF-8 encoding support
    - Preserves line breaks and basic formatting
    - Handles large text files efficiently
"""

import logging
import os
import time
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Tuple
from abc import ABC, abstractmethod

# DeepL imports
try:
    import deepl
    DEEPL_AVAILABLE = True
except ImportError:
    DEEPL_AVAILABLE = False

# OpenAI imports
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Google Translate imports (using simple API key)
try:
    import requests
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

logger = logging.getLogger(__name__)


class BaseTranslator(ABC):
    """Abstract base class for translation providers."""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None):
        """Initialize base translator."""
        self.progress_callback = progress_callback or (lambda x: None)
        self.last_request_time = 0
        self.min_request_interval = 0.01  # Minimum time between requests
    
    @abstractmethod
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text from source to target language."""
        pass
    
    @abstractmethod
    def get_supported_languages(self) -> Tuple[set, set]:
        """Get supported source and target languages."""
        pass
    
    def _rate_limit(self):
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()


class DeepLTranslator(BaseTranslator):
    """DeepL translation provider."""
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """Initialize DeepL translator."""
        super().__init__(progress_callback)
        
        if not DEEPL_AVAILABLE:
            raise ImportError("DeepL library not installed. Install with: pip install deepl")
        
        if not api_key:
            raise ValueError("DeepL API key is required")
        
        try:
            self.translator = deepl.Translator(api_key)
            self.progress_callback("DeepL translator initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize DeepL translator: {e}")
    
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text using DeepL."""
        if not text.strip():
            return text
        
        self._rate_limit()
        
        try:
            # Map language codes to DeepL format
            source_code = self._map_language_code(source_lang, is_source=True)
            target_code = self._map_language_code(target_lang, is_source=False)
            
            result = self.translator.translate_text(
                text,
                source_lang=source_code if source_code != 'auto' else None,
                target_lang=target_code,
                preserve_formatting=True
            )
            return str(result)
        except Exception as e:
            logger.error(f"DeepL translation failed: {e}")
            raise
    
    def get_supported_languages(self) -> Tuple[set, set]:
        """Get DeepL supported languages."""
        try:
            source_langs = {lang.code.lower() for lang in self.translator.get_source_languages()}
            target_langs = {lang.code.lower() for lang in self.translator.get_target_languages()}
            return source_langs, target_langs
        except Exception as e:
            logger.error(f"Failed to get DeepL languages: {e}")
            return set(), set()
    
    def _map_language_code(self, code: str, is_source: bool) -> str:
        """Map language codes to DeepL format."""
        code = code.upper()

        # Handle specific mappings
        mappings = {
            'EN': 'EN-US' if not is_source else 'EN',
            'PT': 'PT-PT' if not is_source else 'PT',
            'ZH': 'ZH-HANS',
            'ZH-HANS': 'ZH-HANS',
            'ZH-HANT': 'ZH-HANT',
            'NB-NO': 'NB',
            'NB': 'NB'
        }

        return mappings.get(code, code)


class GoogleTranslator(BaseTranslator):
    """Google Translate API provider using simple API key authentication."""
    
    def __init__(self, api_key: Optional[str] = None,
                 progress_callback: Optional[Callable[[str], None]] = None):
        """Initialize Google Translate with API key."""
        super().__init__(progress_callback)
        
        if not GOOGLE_AVAILABLE:
            raise ImportError("requests library not installed. Install with: pip install requests")
        
        # Try to get API key from environment or parameters
        if not api_key:
            api_key = os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable or pass api_key parameter")
        
        self.api_key = api_key
        self.base_url = "https://translation.googleapis.com/language/translate/v2"
        self.languages_url = "https://translation.googleapis.com/language/translate/v2/languages"
        self.detect_url = "https://translation.googleapis.com/language/translate/v2/detect"
        
        self.min_request_interval = 0.1  # Rate limiting
        self.progress_callback("Google Translate API initialized with API key")
    
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text using Google Translate API."""
        if not text.strip():
            return text
        
        self._rate_limit()
        
        try:
            # Map language codes to Google format
            target_code = self._map_language_code(target_lang)
            
            # Prepare the request parameters
            params = {
                'key': self.api_key,
                'q': text,
                'target': target_code,
                'format': 'text'
            }
            
            # Add source language if not auto-detect
            if source_lang and source_lang != 'auto':
                source_code = self._map_language_code(source_lang)
                params['source'] = source_code
            
            # Make the API request
            response = requests.post(self.base_url, data=params)
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            
            if 'data' in result and 'translations' in result['data']:
                translations = result['data']['translations']
                if translations and len(translations) > 0:
                    return translations[0]['translatedText']
            
            raise ValueError("No translation returned from Google Translate API")
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise ValueError("Google API key is invalid or Translation API is not enabled. "
                               "Enable it at: https://console.cloud.google.com/apis/library/translate.googleapis.com")
            elif e.response.status_code == 400:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
                raise ValueError(f"Google Translate API error: {error_msg}")
            else:
                raise ValueError(f"Google Translate API HTTP error: {e}")
        except Exception as e:
            logger.error(f"Google Translate failed: {e}")
            raise
    
    def get_supported_languages(self) -> Tuple[set, set]:
        """Get Google Translate supported languages."""
        try:
            # Get the list of supported languages
            params = {
                'key': self.api_key,
                'target': 'en'  # Get language names in English
            }
            
            response = requests.get(self.languages_url, params=params)
            response.raise_for_status()
            
            result = response.json()
            
            if 'data' in result and 'languages' in result['data']:
                languages = result['data']['languages']
                lang_codes = {lang['language'].lower() for lang in languages}
                # Google Translate supports all languages for both source and target
                return lang_codes, lang_codes
            
            raise ValueError("Could not retrieve supported languages")
            
        except Exception as e:
            logger.error(f"Failed to get Google Translate languages: {e}")
            # Return common languages as fallback
            common = {'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 
                     'ar', 'hi', 'fa', 'sw', 'vi', 'th', 'id', 'ms', 'tr', 'pl',
                     'nl', 'sv', 'no', 'da', 'fi', 'cs', 'hu', 'ro', 'bg', 'uk',
                     'he', 'el', 'sr', 'hr', 'sk', 'sl', 'et', 'lv', 'lt', 'is',
                     'mt', 'ga', 'cy', 'eu', 'ca', 'gl', 'sq', 'mk', 'be', 'kk',
                     'uz', 'az', 'hy', 'ka', 'mn', 'ne', 'si', 'km', 'lo', 'my',
                     'tl', 'mg', 'ha', 'yo', 'zu', 'xh', 'af', 'am', 'rn', 'so'}
            return common, common
    
    def detect_language(self, text: str) -> str:
        """Detect the language of the given text."""
        if not text.strip():
            return 'unknown'
        
        self._rate_limit()
        
        try:
            params = {
                'key': self.api_key,
                'q': text
            }
            
            response = requests.post(self.detect_url, data=params)
            response.raise_for_status()
            
            result = response.json()
            
            if 'data' in result and 'detections' in result['data']:
                detections = result['data']['detections']
                if detections and len(detections) > 0 and len(detections[0]) > 0:
                    return detections[0][0]['language']
            
            return 'unknown'
            
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return 'unknown'
    
    def _map_language_code(self, code: str) -> str:
        """Map language codes to Google Translate format."""
        code = code.lower()
        
        # Handle specific mappings for Google Translate API
        mappings = {
            'zh-hans': 'zh-CN',
            'zh-hant': 'zh-TW',
            'nb-no': 'no',
            'nb': 'no',
            'pt-pt': 'pt',
            'pt-br': 'pt',  # Google Translate uses 'pt' for all Portuguese
            'en-us': 'en',
            'en-gb': 'en',
            'sr-latn': 'sr'
        }
        
        return mappings.get(code, code)
    
    def translate_batch(self, texts: list, source_lang: str, target_lang: str) -> list:
        """Translate multiple texts (Google API supports batch in single request)."""
        if not texts:
            return []
        
        self._rate_limit()
        
        try:
            # Map language codes
            target_code = self._map_language_code(target_lang)
            
            # Prepare the request parameters
            params = {
                'key': self.api_key,
                'target': target_code,
                'format': 'text'
            }
            
            # Add source language if not auto-detect
            if source_lang and source_lang != 'auto':
                source_code = self._map_language_code(source_lang)
                params['source'] = source_code
            
            # Add all texts as 'q' parameters (Google supports multiple q parameters)
            data = params.copy()
            data['q'] = texts  # requests will handle the list properly
            
            # Make the API request
            response = requests.post(self.base_url, data=data)
            response.raise_for_status()
            
            # Parse the response
            result = response.json()
            
            translations = []
            if 'data' in result and 'translations' in result['data']:
                for translation in result['data']['translations']:
                    translations.append(translation['translatedText'])
            
            return translations
            
        except Exception as e:
            logger.error(f"Google batch translation failed: {e}")
            # Fallback to individual translations
            return [self.translate_text(text, source_lang, target_lang) for text in texts]


class OpenAITranslator(BaseTranslator):
    """OpenAI GPT translation provider."""
    
    def __init__(self, api_key: str, 
                 model: str = "gpt-4o-mini",
                 progress_callback: Optional[Callable[[str], None]] = None):
        """Initialize OpenAI translator."""
        super().__init__(progress_callback)
        
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI library not installed. Install with: pip install openai")
        
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
        try:
            self.client = OpenAI(api_key=api_key)
            self.model = model
            self.progress_callback(f"OpenAI translator initialized with model {model}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize OpenAI: {e}")
    
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text using OpenAI."""
        if not text.strip():
            return text
        
        self._rate_limit()
        
        try:
            # Map language codes to full names for better GPT understanding
            source_name = self._get_language_name(source_lang)
            target_name = self._get_language_name(target_lang)
            
            system_prompt = f"""You are a professional translator. Translate the following text from {source_name} to {target_name}.
            Preserve the original formatting, tone, and meaning. Only provide the translation, no explanations."""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,  # Lower temperature for more consistent translations
                max_tokens=len(text) * 2  # Allow for expansion in translation
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI translation failed: {e}")
            raise
    
    def get_supported_languages(self) -> Tuple[set, set]:
        """Get OpenAI supported languages (supports most languages)."""
        # OpenAI can handle most languages, return a comprehensive set
        languages = {
            'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'zh-hans', 'zh-hant',
            'ar', 'hi', 'fa', 'sw', 'vi', 'th', 'id', 'ms', 'tr', 'pl', 'nl', 'sv', 'no',
            'da', 'fi', 'cs', 'hu', 'ro', 'bg', 'uk', 'he', 'el', 'sr', 'hr', 'sk', 'sl',
            'et', 'lv', 'lt', 'is', 'mt', 'ga', 'cy', 'eu', 'ca', 'gl', 'sq', 'mk', 'be',
            'kk', 'uz', 'az', 'hy', 'ka', 'mn', 'ne', 'si', 'km', 'lo', 'my', 'tl', 'mg',
            'ha', 'yo', 'zu', 'xh', 'af', 'am', 'rn', 'so', 'ti', 'nb-no', 'sr-latn'
        }
        return languages, languages
    
    def _get_language_name(self, code: str) -> str:
        """Get full language name from code."""
        language_names = {
            'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
            'it': 'Italian', 'pt': 'Portuguese', 'ru': 'Russian', 'ja': 'Japanese',
            'ko': 'Korean', 'zh': 'Chinese', 'zh-hans': 'Chinese Simplified',
            'zh-hant': 'Chinese Traditional', 'ar': 'Arabic', 'hi': 'Hindi',
            'fa': 'Persian/Farsi', 'sw': 'Swahili', 'vi': 'Vietnamese',
            'th': 'Thai', 'id': 'Indonesian', 'ms': 'Malay', 'tr': 'Turkish',
            'pl': 'Polish', 'nl': 'Dutch', 'sv': 'Swedish', 'no': 'Norwegian',
            'nb': 'Norwegian Bokmål', 'nb-no': 'Norwegian Bokmål', 'da': 'Danish',
            'fi': 'Finnish', 'cs': 'Czech', 'hu': 'Hungarian', 'ro': 'Romanian',
            'bg': 'Bulgarian', 'uk': 'Ukrainian', 'he': 'Hebrew', 'el': 'Greek',
            'sr': 'Serbian', 'sr-latn': 'Serbian (Latin)', 'hr': 'Croatian',
            'sk': 'Slovak', 'sl': 'Slovenian', 'et': 'Estonian', 'lv': 'Latvian',
            'lt': 'Lithuanian', 'si': 'Sinhala', 'rn': 'Rundi', 'ha': 'Hausa',
            'auto': 'auto-detect'
        }
        return language_names.get(code.lower(), code)


class MultiProviderTranslator:
    """
    Main translator class that manages multiple translation providers.
    
    This class automatically selects the best provider based on the language pair
    and provider availability. It provides a unified interface for text translation
    regardless of the underlying provider.
    """
    
    def __init__(self, 
                 deepl_api_key: Optional[str] = None,
                 openai_api_key: Optional[str] = None,
                 google_api_key: Optional[str] = None,
                 progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize multi-provider translator.
        
        Args:
            deepl_api_key: DeepL API key
            openai_api_key: OpenAI API key
            google_api_key: Google Translate API key
            progress_callback: Optional callback for progress updates
        """
        self.progress_callback = progress_callback or (lambda x: None)
        self.providers = {}
        
        # Try to get API keys from environment if not provided
        if not deepl_api_key:
            deepl_api_key = os.getenv('DEEPL_API_KEY')
        if not openai_api_key:
            openai_api_key = os.getenv('OPENAI_API_KEY')
        if not google_api_key:
            google_api_key = os.getenv('GOOGLE_API_KEY')
        
        # Initialize available providers
        if deepl_api_key and DEEPL_AVAILABLE:
            try:
                self.providers['deepl'] = DeepLTranslator(deepl_api_key, progress_callback)
                self.progress_callback("DeepL provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize DeepL: {e}")
        
        if openai_api_key and OPENAI_AVAILABLE:
            try:
                self.providers['openai'] = OpenAITranslator(openai_api_key, progress_callback=progress_callback)
                self.progress_callback("OpenAI provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")
        
        if google_api_key and GOOGLE_AVAILABLE:
            try:
                self.providers['google'] = GoogleTranslator(
                    api_key=google_api_key,
                    progress_callback=progress_callback
                )
                self.progress_callback("Google Translate provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Translate: {e}")
        
        if not self.providers:
            raise RuntimeError("No translation providers available. Please configure at least one API key.")
    
    def select_provider(self, source_lang: str, target_lang: str, 
                        preferred_provider: Optional[str] = None) -> str:
        """
        Select the best provider for a language pair.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            preferred_provider: Optional preferred provider name
            
        Returns:
            Selected provider name
        """
        if preferred_provider and preferred_provider in self.providers:
            return preferred_provider
        
        # Check DeepL first (best quality for European languages)
        if 'deepl' in self.providers:
            source_langs, target_langs = self.providers['deepl'].get_supported_languages()
            if source_lang.lower() in source_langs and target_lang.lower() in target_langs:
                return 'deepl'
        
        # Then Google (broad language support)
        if 'google' in self.providers:
            return 'google'
        
        # Finally OpenAI (can handle any language but may be slower/more expensive)
        if 'openai' in self.providers:
            return 'openai'
        
        # Use first available provider
        return list(self.providers.keys())[0]
    
    def translate_text(self, text: str, source_lang: str, target_lang: str,
                      preferred_provider: Optional[str] = None) -> str:
        """
        Translate text using the best available provider.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            preferred_provider: Optional preferred provider
            
        Returns:
            Translated text
        """
        if not text.strip():
            return text
        
        provider_name = self.select_provider(source_lang, target_lang, preferred_provider)
        provider = self.providers[provider_name]
        
        self.progress_callback(f"Using {provider_name} for translation")
        return provider.translate_text(text, source_lang, target_lang)
    
    def translate_text_file(self, input_path: Path, output_path: Path,
                           source_lang: str, target_lang: str,
                           preferred_provider: Optional[str] = None) -> bool:
        """
        Translate a text file.
        
        Args:
            input_path: Path to input file
            output_path: Path to output file
            source_lang: Source language code
            target_lang: Target language code
            preferred_provider: Optional preferred provider
            
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
            translated_text = self.translate_text(
                text, source_lang, target_lang, preferred_provider
            )
            
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
    
    def get_available_providers(self) -> list:
        """Get list of available providers."""
        return list(self.providers.keys())
    
    def get_supported_languages(self, provider: Optional[str] = None) -> Dict[str, Tuple[set, set]]:
        """
        Get supported languages for each provider.
        
        Args:
            provider: Optional specific provider name
            
        Returns:
            Dictionary mapping provider names to (source_langs, target_langs) tuples
        """
        result = {}
        
        if provider:
            if provider in self.providers:
                source, target = self.providers[provider].get_supported_languages()
                result[provider] = (source, target)
        else:
            for name, prov in self.providers.items():
                source, target = prov.get_supported_languages()
                result[name] = (source, target)
        
        return result


# Maintain backward compatibility with existing code
class TextTranslationCore(MultiProviderTranslator):
    """
    Backward compatible wrapper for existing code.
    Defaults to DeepL if available, otherwise uses any available provider.
    """
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """Initialize with DeepL API key for backward compatibility."""
        super().__init__(
            deepl_api_key=api_key,
            progress_callback=progress_callback
        )