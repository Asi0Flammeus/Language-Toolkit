import sys
import logging

from pathlib import Path

sys.path.append("../")
from tools.tool_base import ToolBase
from config.config_manager import ConfigManager

class AudioTranscriptionTool(ToolBase):
    """Transcribes audio files to text files."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.api_key = config_manager.get_api_keys().get("openai", None) # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Transcribes a single audio file."""
        if input_file.suffix.lower() not in [".mp3", ".wav", ".m4a"]:
            self.send_progress_update(f"Skipping unsupported audio file: {input_file}")
            return

        try:
            self.send_progress_update(f"Transcribing {input_file.name}...")

            # Transcription logic (replace with your actual transcription API call)
            transcript = self.transcribe_audio(input_file)

            output_file = output_dir / f"{input_file.stem}_transcript.txt"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(transcript)

            self.send_progress_update(f"Successfully transcribed {input_file.name} to {output_file.name}")

        except Exception as e:
            error_message = f"Error transcribing {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def transcribe_audio(self, audio_file: Path) -> str:
        """
        Placeholder for audio transcription API call.  Replace with your actual
        transcription logic (e.g., using OpenAI Whisper API).
        """
        #Mock transcription
        return f"Transcript of {audio_file.name}"

