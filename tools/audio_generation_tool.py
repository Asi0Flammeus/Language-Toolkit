import tkinter as tk
import logging
import sys

from pathlib import Path

sys.path.append("../")
from tools.tool_base import ToolBase
#Import in order to load from the api keys

from config.config_manager import ConfigManager

class AudioGenerationTool(ToolBase):
    """Generates audio from text files using ElevenLabs."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.voice_id = tk.StringVar()  # Voice ID for ElevenLabs
        self.elevenlabs_config = config_manager.get_elevenlabs_config() # Load elevenlabs config
        self.api_key = config_manager.get_api_keys().get("elevenlabs", None) # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Generates audio from a single text file."""
        if input_file.suffix.lower() != ".txt":
            self.send_progress_update(f"Skipping non-TXT file: {input_file}")
            return

        try:
            self.send_progress_update(f"Generating audio from {input_file.name}...")
            with open(input_file, "r", encoding="utf-8") as f:
                text = f.read()

            # Audio generation logic (replace with your actual ElevenLabs API call)
            audio_file = self.generate_audio(text, self.voice_id.get())

            output_file = output_dir / f"{input_file.stem}.mp3"
            # Save the audio file
            self.send_progress_update(f"Successfully generated audio from {input_file.name} to {output_file.name}")

        except Exception as e:
            error_message = f"Error generating audio from {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def generate_audio(self, text: str, voice_id: str) -> Path:
        """
        Placeholder for audio generation API call.  Replace with your actual
        ElevenLabs API logic.
        """
        #Mock audio generation
        return Path("dummy_audio.mp3")


