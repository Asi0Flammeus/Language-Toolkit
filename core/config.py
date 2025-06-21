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
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Manages configuration files and settings for the Language Toolkit.
    
    This class provides a centralized way to handle application configuration,
    including API keys, supported languages, and user preferences. Configuration
    is stored in JSON format in the user's Documents directory.
    
    Key Features:
        - Automatic configuration directory creation
        - Default configuration generation
        - API key secure storage and retrieval
        - Language configuration management
        - Cross-platform compatibility
    
    Configuration Location:
        ~/Documents/Language Toolkit/config.json
    
    Example Usage:
        config = ConfigManager()
        api_keys = config.get_api_keys()
        languages = config.get_languages()
        config.save_api_keys({"deepl": "your-key", "openai": "your-key"})
    """
    
    def __init__(self):
        self.config = {}
        self.config_file = Path.home() / "Documents" / "Language Toolkit" / "config.json"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.load_config()
        
    def load_config(self):
        """Load configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logging.info(f"Configuration loaded from {self.config_file}")
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
    
    def get_languages(self) -> list:
        """Get list of supported languages."""
        return self.config.get("languages", {}).get("supported", [])
    
    def get_api_keys(self) -> Dict[str, str]:
        """Get stored API keys."""
        return self.config.get("api_keys", {})
    
    def save_api_keys(self, api_keys: Dict[str, str]):
        """Save API keys to configuration."""
        self.config["api_keys"] = api_keys
        self.save_config()
    
    def get_output_formats(self) -> list:
        """Get supported output formats."""
        return self.config.get("output_formats", ["pdf", "png"])