# language_toolkit/config/config_manager.py

import json
import logging
from pathlib import Path
from dotenv import load_dotenv
import os

SCRIPT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(SCRIPT_DIR / ".env") # Load .env file

SUPPORTED_LANGUAGES_FILE = SCRIPT_DIR / "supported_languages.json"
ELEVENLABS_CONFIG_FILE = SCRIPT_DIR / "elevenlabs_config.json"
API_KEYS_FILE = SCRIPT_DIR / "api_keys.json"


class ConfigManager:
    """Manages configuration files for the application."""

    def __init__(self, languages_file=SUPPORTED_LANGUAGES_FILE,
                 elevenlabs_file=ELEVENLABS_CONFIG_FILE, api_keys_file=API_KEYS_FILE):
        self.languages_file = Path(languages_file)
        self.elevenlabs_file = Path(elevenlabs_file)
        self.api_keys_file = Path(api_keys_file)

        self.languages = self.load_json(self.languages_file)
        self.elevenlabs_config = self.load_json(self.elevenlabs_file)
        self.api_keys = self.load_json(self.api_keys_file)

    def load_json(self, file_path: Path):
        """Loads JSON data from a file."""
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.warning(f"Config file not found: {file_path}.  Creating a default.")
            return {}  # Return an empty dictionary if the file doesn't exist
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON from {file_path}.  Please check the file for errors.")
            return {}

    def save_json(self, data, file_path: Path):
        """Saves JSON data to a file."""
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4,ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving to {file_path}: {e}")

    def get_languages(self):
        return self.languages

    def get_elevenlabs_config(self):
        return self.elevenlabs_config

    def get_api_keys(self):
        # Load from .env and json file
        api_keys = self.api_keys
        # override with the content of the env
        for api_name in ["openai", "anthropic", "deepl", "adobe", "elevenlabs", "google"]:
            api_keys[api_name] = os.getenv(f"API_KEY_{api_name.upper()}") or api_keys.get(api_name)
        return api_keys

    def save_languages(self):
         self.save_json(self.languages, self.languages_file)

    def save_elevenlabs_config(self):
        self.save_json(self.elevenlabs_config, self.elevenlabs_file)

    def save_api_keys(self,api_keys):
        # no save needed since the dot env should not be automatically modified by the app!
        self.save_json(api_keys, self.api_keys_file)

