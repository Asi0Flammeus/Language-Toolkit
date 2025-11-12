"""
Configuration Management Core Module

This module provides configuration management functionality for the Language Toolkit.
It handles loading, saving, and managing application settings, API keys, and supported languages.

Usage Examples:
    GUI: Used to store user preferences, API keys, and language selections
    API: Used to load API keys for service authentication and language validation
    
Features:
    - JSON-based configuration storage
    - Secure API key management
    - Language support configuration
    - Default settings initialization
    - Cross-platform configuration directory handling
    - Support for project-local language files
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Import file utilities for consistent file operations
try:
    from .file_utils import load_json_file, save_json_file
except ImportError:
    # Fallback for when file_utils is not available
    def load_json_file(path, default=None, create_if_missing=False):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default if default is not None else {}
    
    def save_json_file(path, data, indent=4, ensure_ascii=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        return True

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Manages configuration files and settings for the Language Toolkit.
    
    This class provides a centralized way to handle application configuration,
    including API keys, supported languages, and user preferences. Configuration
    is stored in JSON format in the user's Documents directory or project directory.
    
    Key Features:
        - Automatic configuration directory creation
        - Default configuration generation
        - API key secure storage and retrieval
        - Language configuration management
        - Cross-platform compatibility
        - Project-local API key support
    
    Configuration Location:
        ~/Documents/Language Toolkit/config.json (default)
        ./api_keys.json (project-local for API keys)
    
    Example Usage:
        config = ConfigManager()
        api_keys = config.get_api_keys()
        languages = config.get_languages()
        config.save_api_keys({"deepl": "your-key", "openai": "your-key"})
        
        # For project-local API keys
        config = ConfigManager(use_project_api_keys=True)
    """
    
    def __init__(self, 
                 use_project_api_keys: bool = False,
                 languages_file: Optional[str] = None,
                 api_keys_file: Optional[str] = None):
        """
        Initialize ConfigManager.
        
        Args:
            use_project_api_keys: Use project-local api_keys.json instead of global config
            languages_file: Project-local languages file (e.g., "supported_languages.json")
            api_keys_file: Project-local API keys file (for backward compatibility)
        """
        self.config = {}
        self.use_project_api_keys = use_project_api_keys
        self._api_keys_cache = None  # Cache for API keys
        self._api_keys_loaded = False  # Track if we've already logged about API keys
        
        # File paths
        self.project_root = Path(__file__).parent.parent
        self.config_file = Path.home() / "Documents" / "Language Toolkit" / "config.json"
        self.project_api_keys_file = self.project_root / (api_keys_file or "api_keys.json")
        self.project_languages_file = self.project_root / (languages_file or "supported_languages.json")
        
        # Ensure config directory exists
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load environment variables
        env_path = self.project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
        
        self.load_config()
        
    def load_config(self):
        """Load configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logging.debug(f"Configuration loaded from {self.config_file}")
            else:
                self.config = self.get_default_config()
                self.save_config()
                logging.info("Created default configuration")
        except Exception as e:
            logging.error(f"Failed to load configuration: {e}")
            self.config = self.get_default_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration settings."""
        return {
            "languages": {
                "supported": [
                    {"code": "en", "name": "English"},
                    {"code": "fr", "name": "French"},
                    {"code": "es", "name": "Spanish"},
                    {"code": "de", "name": "German"},
                    {"code": "it", "name": "Italian"},
                    {"code": "pt", "name": "Portuguese"},
                    {"code": "ru", "name": "Russian"},
                    {"code": "ja", "name": "Japanese"},
                    {"code": "ko", "name": "Korean"},
                    {"code": "zh", "name": "Chinese (Simplified)"},
                    {"code": "ar", "name": "Arabic"},
                    {"code": "hi", "name": "Hindi"},
                    {"code": "tr", "name": "Turkish"},
                    {"code": "pl", "name": "Polish"},
                    {"code": "nl", "name": "Dutch"},
                    {"code": "sv", "name": "Swedish"},
                    {"code": "da", "name": "Danish"},
                    {"code": "no", "name": "Norwegian"},
                    {"code": "fi", "name": "Finnish"},
                    {"code": "he", "name": "Hebrew"}
                ]
            },
            "api_keys": {},
            "output_formats": ["pdf", "png"]
        }
    
    def save_config(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logging.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}")
    
    def get_languages(self) -> Dict[str, Any]:
        """
        Get supported languages configuration.
        
        Tries project-local languages file first, then falls back to global config.
        
        Returns:
            Dictionary with language configuration. Format depends on the source:
            - Project file: Raw JSON content (e.g., {"source_languages": {...}, "target_languages": {...}})
            - Global config: {"supported": [...]} format
        """
        # Try project-local languages file first
        if self.project_languages_file.exists():
            try:
                languages = load_json_file(self.project_languages_file, default={})
                if languages:
                    logger.debug(f"Loaded languages from {self.project_languages_file}")
                    return languages
            except Exception as e:
                logger.warning(f"Failed to load project languages file: {e}")
        
        # Fall back to global config
        return self.config.get("languages", {})
    
    def save_languages(self, languages: Dict[str, Any]) -> None:
        """
        Save languages configuration.
        
        Args:
            languages: Language configuration to save
        """
        if self.project_languages_file.parent.exists():
            # Save to project-local file if project structure exists
            try:
                save_json_file(self.project_languages_file, languages)
                logger.info(f"Saved languages to {self.project_languages_file}")
                return
            except Exception as e:
                logger.warning(f"Failed to save to project languages file: {e}")
        
        # Fall back to global config
        self.config["languages"] = languages
        self.save_config()
        logger.info("Saved languages to global config")
    
    def get_api_keys(self) -> Dict[str, str]:
        """Get stored API keys - prioritize .env over JSON files."""
        # Return cached keys if already loaded
        if self._api_keys_cache is not None:
            return self._api_keys_cache
        
        api_keys = {}
        
        # First try to get keys from environment variables
        env_mapping = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY", 
            "deepl": "DEEPL_API_KEY",
            "google": "GOOGLE_API_KEY",
            "convertapi": "CONVERTAPI_KEY",
            "elevenlabs": "ELEVENLABS_API_KEY"
        }
        
        for key, env_var in env_mapping.items():
            env_value = os.getenv(env_var)
            if env_value:
                api_keys[key] = env_value
        
        # If we got keys from env, cache and return them
        if api_keys:
            if not self._api_keys_loaded:
                logger.info("API keys loaded successfully")
                self._api_keys_loaded = True
            self._api_keys_cache = api_keys
            return api_keys
        
        # Otherwise fall back to JSON files
        if self.use_project_api_keys:
            # Load API keys from project-local file
            try:
                if self.project_api_keys_file.exists():
                    with open(self.project_api_keys_file, 'r', encoding='utf-8') as f:
                        project_keys = json.load(f)
                    if not self._api_keys_loaded:
                        logger.info("API keys loaded successfully")
                        self._api_keys_loaded = True
                    self._api_keys_cache = project_keys
                    return project_keys
            except Exception as e:
                logger.warning(f"Failed to load project API keys: {e}")
        
        # Fall back to global config
        config_keys = self.config.get("api_keys", {})
        if config_keys and not self._api_keys_loaded:
            logger.info("API keys loaded successfully")
            self._api_keys_loaded = True
        
        self._api_keys_cache = config_keys
        return config_keys
    
    def save_api_keys(self, api_keys: Dict[str, str]):
        """Save API keys to configuration."""
        self.config["api_keys"] = api_keys
        self.save_config()
    
    def get_output_formats(self) -> list:
        """Get supported output formats."""
        return self.config.get("output_formats", ["pdf", "png"])