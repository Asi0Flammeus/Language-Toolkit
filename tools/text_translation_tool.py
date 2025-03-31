import tkinter as tk
import sys
import logging

from pathlib import Path

sys.path.append("../")
from tools.tool_base import ToolBase
from config.config_manager import ConfigManager

class TextTranslationTool(ToolBase):
    """Translates text files from one language to another."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.source_lang = tk.StringVar(value="en")  # Default source language
        self.target_lang = tk.StringVar(value="fr")  # Default target language
        self.api_key = config_manager.get_api_keys().get("deepl", None) # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Translates a single text file."""
        if input_file.suffix.lower() != ".txt":
            self.send_progress_update(f"Skipping non-TXT file: {input_file}")
            return

        try:
            self.send_progress_update(f"Translating {input_file.name}...")
            with open(input_file, "r", encoding="utf-8") as f:
                text = f.read()

            # Translation logic (replace with your actual translation API call)
            translated_text = self.translate_text(text, self.source_lang.get(), self.target_lang.get())

            output_file = output_dir / f"{input_file.stem}_translated.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(translated_text)

            self.send_progress_update(f"Successfully translated {input_file.name} to {output_file.name}")

        except Exception as e:
            error_message = f"Error translating {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
         """
         Placeholder for translation API call.  Replace with your actual
         translation logic (e.g., using DeepL, Google Translate, etc.).
         """
         #Mock translation
         return f"Translated text from {source_lang} to {target_lang}: {text}"

