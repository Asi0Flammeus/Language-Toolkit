"""Text translation tool using DeepL API."""

import tkinter as tk
import logging
from pathlib import Path

from ui.base_tool import ToolBase
from ui.mixins import LanguageSelectionMixin
from core.processors import ProgressReporter, ProcessorConfig, create_translation_processor


class TextTranslationTool(ToolBase, LanguageSelectionMixin):
    """Translates text files using DeepL API."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        
        # Define supported extensions
        self.supported_extensions = {'.txt'}
        
        # Language selection variables
        self.source_lang = tk.StringVar(value="en")
        self.target_lang = tk.StringVar(value="fr")
        
        # Get API key
        self.api_key = self.config_manager.get_api_keys().get("deepl")
        if not self.api_key:
            logging.warning("DeepL API key not configured")

    def process_file(self, input_file: Path, output_dir: Path):
        """Processes a single text file using consolidated translation processor."""
        try:
            # Check for interruption
            if self.stop_flag.is_set():
                raise InterruptedError("Processing stopped by user")

            # Create output filename with target language suffix
            output_filename = f"{input_file.stem}_{self.target_lang.get()}{input_file.suffix}"
            output_file = output_dir / output_filename
            
            # Create translation processor with GUI-specific progress reporter
            progress_reporter = ProgressReporter(callback=lambda msg: (
                self.send_progress_update(msg) if not self.stop_flag.is_set() 
                else (_ for _ in ()).throw(InterruptedError("Processing stopped by user"))
            ))
            
            processor = create_translation_processor(
                self.service_manager, 
                progress_reporter=progress_reporter,
                config=ProcessorConfig(
                    skip_existing=self.check_output_exists.get(),
                    allowed_extensions={'.txt'},
                    max_file_size_mb=50.0
                )
            )
            
            # Process the file using consolidated processor
            result = processor.process_file(
                input_file, 
                output_file,
                source_language=self.source_lang.get(),
                target_language=self.target_lang.get()
            )
            
            if result.success:
                self.send_progress_update(f"Successfully translated: {input_file.name}")
            elif result.skipped:
                # Skip message already sent by processor
                pass
            else:
                self.send_progress_update(f"Failed to translate: {input_file.name} - {result.message}")

        except InterruptedError:
            raise
        except Exception as e:
            error_message = f"Error translating {input_file.name}: {str(e)}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

    def before_processing(self):
        """Pre-processing setup."""
        if not self.api_key:
            raise ValueError("DeepL API key not configured. Please add your API key in the Configuration menu.")

    def after_processing(self):
        """Post-processing cleanup."""
        pass