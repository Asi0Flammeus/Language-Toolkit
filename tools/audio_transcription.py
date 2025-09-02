"""Audio transcription tool using OpenAI's Whisper API."""

import logging
from pathlib import Path

from ui.base_tool import ToolBase
from core.processors import ProgressReporter, ProcessorConfig, create_audio_processor


class AudioTranscriptionTool(ToolBase):
    """Transcribes audio files using OpenAI's Whisper API via AudioTranscriptionCore."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        # Define supported extensions
        self.supported_extensions = {'.wav', '.mp3', '.m4a', '.webm', 
                                   '.mp4', '.mpga', '.mpeg'}

        # Get OpenAI API key from config
        self.api_key = self.config_manager.get_api_keys().get("openai")
        if not self.api_key:
            logging.warning("OpenAI API key not configured")

    def process_file(self, input_file: Path, output_dir: Path):
        """Processes a single audio file using consolidated audio processor."""
        try:
            # Check if processing should stop
            if self.stop_flag.is_set():
                raise InterruptedError("Processing stopped by user")
            
            # Create output filename with transcript suffix
            output_filename = f"{input_file.stem}_transcript.txt"
            output_path = output_dir / output_filename
            
            # Create audio processor with GUI-specific progress reporter
            progress_reporter = ProgressReporter(callback=lambda msg: (
                self.send_progress_update(msg) if not self.stop_flag.is_set() 
                else (_ for _ in ()).throw(InterruptedError("Processing stopped by user"))
            ))
            
            processor = create_audio_processor(
                self.service_manager,
                progress_reporter=progress_reporter,
                config=ProcessorConfig(
                    skip_existing=self.check_output_exists.get(),
                    allowed_extensions=self.supported_extensions,
                    max_file_size_mb=100.0
                )
            )
            
            # Process the file using consolidated processor
            result = processor.process_file(
                input_file,
                output_path,
                operation='transcribe'
            )
            
            if result.success:
                self.send_progress_update(f"Successfully transcribed: {input_file.name}")
            elif result.skipped:
                # Skip message already sent by processor
                pass
            else:
                self.send_progress_update(f"Failed to transcribe: {input_file.name} - {result.message}")

        except InterruptedError:
            raise
        except Exception as e:
            error_message = f"Error transcribing {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)