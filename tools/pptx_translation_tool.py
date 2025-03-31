import logging
import sys
import tkinter as tk

from pathlib import Path

sys.path.append("../")
from tools.tool_base import ToolBase
from config.config_manager import ConfigManager

class PPTXTranslationTool(ToolBase):
    """Translates PPTX files from one language to another."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.source_lang = tk.StringVar(value="en")  # Default source language
        self.target_lang = tk.StringVar(value="fr")  # Default target language
        self.api_key = config_manager.get_api_keys().get("deepl", None) # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Translates a single PPTX file."""
        if input_file.suffix.lower() != ".pptx":
            self.send_progress_update(f"Skipping non-PPTX file: {input_file}")
            return

        try:
            self.send_progress_update(f"Translating {input_file.name}...")

            # Translation logic (replace with your actual translation API call)
            translated_file = self.translate_pptx(input_file, self.source_lang.get(), self.target_lang.get(), output_dir)

            self.send_progress_update(f"Successfully translated {input_file.name} to {translated_file.name}")

        except Exception as e:
            error_message = f"Error translating {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def translate_pptx(self, input_file: Path, source_lang: str, target_lang: str, output_dir: Path) -> Path:
        """
        Placeholder for PPTX translation API call.  Replace with your actual
        translation logic (e.g., using DeepL).
        """
        #Mock translation
        return Path("dummy_translated.pptx")

