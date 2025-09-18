"""
Configuration-based Text Translation Module

This module provides text translation using provider configuration from language_providers.json.
It automatically selects the appropriate provider and maps language codes correctly.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any, Tuple

# Import the existing multi-provider translator
from .text_translation_multi import (
    MultiProviderTranslator,
    DeepLTranslator,
    GoogleTranslator,
    OpenAITranslator,
    DEEPL_AVAILABLE,
    GOOGLE_AVAILABLE,
    OPENAI_AVAILABLE
)

logger = logging.getLogger(__name__)


class ConfigBasedTranslator:
    """
    Translator that uses language_providers.json to determine which provider
    to use for each language and how to map language codes.
    """
    
    def __init__(self, 
                 config_file: Optional[str] = None,
                 deepl_api_key: Optional[str] = None,
                 openai_api_key: Optional[str] = None,
                 google_api_key: Optional[str] = None,
                 progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize configuration-based translator.
        
        Args:
            config_file: Path to language_providers.json (defaults to project root)
            deepl_api_key: DeepL API key
            openai_api_key: OpenAI API key
            google_api_key: Google Translate API key
            progress_callback: Optional callback for progress updates
        """
        self.progress_callback = progress_callback or (lambda x: None)
        
        # Load language configuration
        self.config = self._load_config(config_file)
        self.language_map = self._build_language_map()
        
        # Try to get API keys from environment if not provided
        if not deepl_api_key:
            deepl_api_key = os.getenv('DEEPL_API_KEY')
        if not openai_api_key:
            openai_api_key = os.getenv('OPENAI_API_KEY')
        if not google_api_key:
            google_api_key = os.getenv('GOOGLE_API_KEY')
        
        # Initialize providers
        self.providers = {}
        
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
        
        self.progress_callback(f"Loaded configuration with {len(self.language_map)} languages")
    
    def _load_config(self, config_file: Optional[str] = None) -> Dict[str, Any]:
        """Load language configuration from JSON file."""
        if not config_file:
            # Default to language_providers.json in project root
            project_root = Path(__file__).parent.parent
            config_file = project_root / "language_providers.json"
        else:
            config_file = Path(config_file)
        
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
    
    def _build_language_map(self) -> Dict[str, Dict[str, str]]:
        """Build a map of language codes to provider and translator codes."""
        language_map = {}
        
        for lang in self.config.get('languages', []):
            code = lang['code']
            language_map[code] = {
                'name': lang['name'],
                'provider': lang['translator'],
                'provider_code': lang['code_translator']
            }
            
            # Also map common variants
            if code == 'zh-Hans':
                language_map['zh'] = language_map[code].copy()
                language_map['zh-CN'] = language_map[code].copy()
                language_map['zh-cn'] = language_map[code].copy()
            elif code == 'zh-Hant':
                language_map['zh-TW'] = language_map[code].copy()
                language_map['zh-tw'] = language_map[code].copy()
            elif code == 'nb-NO':
                language_map['nb'] = language_map[code].copy()
                language_map['no'] = language_map[code].copy()
            elif code == 'pt':
                language_map['pt-PT'] = language_map[code].copy()
                language_map['pt-pt'] = language_map[code].copy()
            elif code == 'en':
                language_map['en-US'] = language_map[code].copy()
                language_map['en-us'] = language_map[code].copy()
                language_map['en-GB'] = language_map[code].copy()
                language_map['en-gb'] = language_map[code].copy()
        
        return language_map
    
    def get_language_info(self, lang_code: str) -> Optional[Dict[str, str]]:
        """Get language information for a given code."""
        # Try exact match first
        if lang_code in self.language_map:
            return self.language_map[lang_code]
        
        # Try case-insensitive match
        for code, info in self.language_map.items():
            if code.lower() == lang_code.lower():
                return info
        
        return None
    
    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Translate text using the appropriate provider based on configuration.
        
        Args:
            text: Text to translate
            source_lang: Source language code (user-facing code)
            target_lang: Target language code (user-facing code)
            
        Returns:
            Translated text
        """
        if not text.strip():
            return text
        
        # Get language information
        source_info = self.get_language_info(source_lang)
        target_info = self.get_language_info(target_lang)
        
        if not target_info:
            raise ValueError(f"Unsupported target language: {target_lang}")
        
        # Determine which provider to use (based on target language)
        provider_name = target_info['provider']
        
        if provider_name not in self.providers:
            # Try to find an alternative provider
            available = list(self.providers.keys())
            if available:
                provider_name = available[0]
                logger.warning(f"Provider '{target_info['provider']}' not available for {target_lang}, using {provider_name}")
            else:
                raise RuntimeError(f"No provider available for language {target_lang}")
        
        provider = self.providers[provider_name]
        
        # Map language codes to provider-specific codes
        if provider_name == 'deepl':
            # DeepL uses uppercase codes
            source_code = source_info['provider_code'] if source_info else source_lang.upper()
            target_code = target_info['provider_code']
            
            # DeepL-specific mappings
            if source_code == 'EN-US':
                source_code = 'EN'  # DeepL uses EN for source
            elif source_code == 'PT-PT':
                source_code = 'PT'  # DeepL uses PT for source
                
        elif provider_name == 'google':
            # Google uses lowercase codes
            source_code = source_info['provider_code'].lower() if source_info else source_lang.lower()
            target_code = target_info['provider_code'].lower()
            
        elif provider_name == 'openai':
            # OpenAI can use the language names or codes
            source_code = source_info['name'] if source_info else source_lang
            target_code = target_info['name']
        
        else:
            # Default: use the provider codes as-is
            source_code = source_info['provider_code'] if source_info else source_lang
            target_code = target_info['provider_code']
        
        # Handle auto-detect
        if source_lang == 'auto':
            source_code = 'auto'
        
        self.progress_callback(f"Translating {source_lang}→{target_lang} using {provider_name}")
        
        # Perform the translation
        return provider.translate_text(text, source_code, target_code)
    
    def translate_batch(self, texts: list, source_lang: str, target_lang: str) -> list:
        """
        Translate multiple texts using the appropriate provider.
        
        Args:
            texts: List of texts to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            List of translated texts
        """
        if not texts:
            return []
        
        # Get language information
        source_info = self.get_language_info(source_lang)
        target_info = self.get_language_info(target_lang)
        
        if not target_info:
            raise ValueError(f"Unsupported target language: {target_lang}")
        
        # Determine provider
        provider_name = target_info['provider']
        
        if provider_name not in self.providers:
            available = list(self.providers.keys())
            if available:
                provider_name = available[0]
            else:
                raise RuntimeError(f"No provider available for language {target_lang}")
        
        provider = self.providers[provider_name]
        
        # Check if provider supports batch translation
        if hasattr(provider, 'translate_batch'):
            # Map codes and use batch translation
            if provider_name == 'deepl':
                source_code = source_info['provider_code'] if source_info else source_lang.upper()
                target_code = target_info['provider_code']
                if source_code == 'EN-US':
                    source_code = 'EN'
                elif source_code == 'PT-PT':
                    source_code = 'PT'
            elif provider_name == 'google':
                source_code = source_info['provider_code'].lower() if source_info else source_lang.lower()
                target_code = target_info['provider_code'].lower()
            else:
                source_code = source_info['name'] if source_info else source_lang
                target_code = target_info['name']
            
            if source_lang == 'auto':
                source_code = 'auto'
            
            return provider.translate_batch(texts, source_code, target_code)
        else:
            # Fall back to individual translations
            return [self.translate_text(text, source_lang, target_lang) for text in texts]
    
    def get_supported_languages(self) -> Dict[str, list]:
        """Get list of supported languages organized by provider."""
        result = {
            'all': [],
            'by_provider': {}
        }
        
        for lang_code, info in self.language_map.items():
            # Skip variants
            if '-' not in lang_code or lang_code in ['zh-Hans', 'zh-Hant', 'nb-NO', 'sr-Latn']:
                lang_entry = {
                    'code': lang_code,
                    'name': info['name'],
                    'provider': info['provider']
                }
                result['all'].append(lang_entry)
                
                # Organize by provider
                provider = info['provider']
                if provider not in result['by_provider']:
                    result['by_provider'][provider] = []
                result['by_provider'][provider].append(lang_entry)
        
        return result
    
    def get_available_providers(self) -> list:
        """Get list of initialized providers."""
        return list(self.providers.keys())
    
    def validate_language_pair(self, source_lang: str, target_lang: str) -> Tuple[bool, str]:
        """
        Validate if a language pair is supported.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        source_info = self.get_language_info(source_lang) if source_lang != 'auto' else {'provider': 'auto'}
        target_info = self.get_language_info(target_lang)
        
        if not target_info:
            return False, f"Target language '{target_lang}' is not supported"
        
        if source_lang != 'auto' and not source_info:
            return False, f"Source language '{source_lang}' is not supported"
        
        # Check if the required provider is available
        required_provider = target_info['provider']
        if required_provider not in self.providers:
            available = ', '.join(self.providers.keys())
            return False, f"Provider '{required_provider}' required for {target_lang} is not available. Available: {available}"
        
        return True, "Language pair is supported"


# Maintain backward compatibility
class TextTranslationCore(ConfigBasedTranslator):
    """
    Backward compatible wrapper that uses configuration-based translation.
    """
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """Initialize with a single API key for backward compatibility."""
        # Try to determine which provider the API key is for
        deepl_key = None
        google_key = None
        openai_key = None
        
        # Simple heuristic: DeepL keys often have a specific format
        if ':fx' in api_key:
            deepl_key = api_key
        else:
            # Default to Google for simple API keys
            google_key = api_key
        
        super().__init__(
            deepl_api_key=deepl_key,
            google_api_key=google_key,
            openai_api_key=openai_key,
            progress_callback=progress_callback
        )
    
    def translate_text_file(self, input_path: Path, output_path: Path,
                           source_lang: str, target_lang: str) -> bool:
        """Translate a text file."""
        try:
            self.progress_callback(f"Reading text file: {input_path}")
            
            with open(input_path, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if not text.strip():
                raise ValueError("Input file is empty")
            
            self.progress_callback("Translating text...")
            translated_text = self.translate_text(text, source_lang, target_lang)
            
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