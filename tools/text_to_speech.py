"""Text to Speech tool for converting text files to MP3 audio."""

import logging
from pathlib import Path

from ui.base_tool import ToolBase
from core.processors import ProgressReporter, ProcessorConfig, create_audio_processor


class TextToSpeechTool(ToolBase):
    """
    Converts text files (.txt) to MP3 audio using the ElevenLabs API.
    Uses TextToSpeechCore for the actual processing with filename-based voice selection.
    Voice name can be separated by underscore, hyphen, or space.
    """

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.supported_extensions = {'.txt'}
        self.config_manager = config_manager

    def before_processing(self):
        """Pre-processing setup."""
        api_key = self.config_manager.get_api_keys().get("elevenlabs")
        if not api_key:
            raise ValueError("ElevenLabs API key not configured. Please add your API key in the Configuration menu.")

    def process_file(self, input_file: Path, output_dir: Path):
        """Processes a single text file for TTS conversion using consolidated audio processor."""
        try:
            # Check for interruption
            if self.stop_flag.is_set():
                raise InterruptedError("Processing stopped by user")
            
            # Determine output path
            output_file = output_dir / f"{input_file.stem}.mp3"
            
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
                    allowed_extensions={'.txt'},
                    max_file_size_mb=10.0
                )
            )
            
            # Process the file using consolidated processor
            result = processor.process_file(
                input_file,
                output_file,
                operation='synthesize'
            )
            
            if result.success:
                self.send_progress_update(f"Successfully generated audio: {output_file.name}")
            elif result.skipped:
                # Skip message already sent by processor
                pass
            else:
                self.send_progress_update(f"Failed to generate audio for: {input_file.name} - {result.message}")
            
        except InterruptedError:
            raise
        except Exception as e:
            error_message = f"Error generating audio for {input_file.name}: {str(e)}"
            self.send_progress_update(error_message)
            logging.exception(error_message)