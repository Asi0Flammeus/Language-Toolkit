"""PPTX to PDF/PNG/WEBP conversion tool using ConvertAPI."""

import tkinter as tk
from tkinter import ttk
import logging
from pathlib import Path

from ui.base_tool import ToolBase
from core.processors import ProgressReporter, ProcessorConfig, create_conversion_processor


class PPTXtoPDFTool(ToolBase):
    """
    Converts PPTX files to PDF, PNG, or WEBP using ConvertAPI service.
    Supports PDF conversion, PNG conversion (one PNG per slide), and WEBP conversion (PNG to WEBP).
    """

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.supported_extensions = {'.pptx', '.ppt', '.potx', '.pps', '.ppsx'}
        self.output_format = tk.StringVar(value="pdf")  # Default to PDF

    def create_specific_controls(self, parent_frame):
        """Creates UI elements specific to this tool (output format selection)."""
        format_frame = ttk.LabelFrame(parent_frame, text="Output Format")
        format_frame.pack(fill='x', padx=5, pady=5)

        ttk.Radiobutton(format_frame, text="PDF",
                       variable=self.output_format,
                       value="pdf").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(format_frame, text="PNG (One per slide)",
                       variable=self.output_format,
                       value="png").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(format_frame, text="WEBP (One per slide)",
                       variable=self.output_format,
                       value="webp").pack(side=tk.LEFT, padx=10)

    def before_processing(self):
        """Load credentials before starting the batch."""
        api_keys = self.config_manager.get_api_keys()
        api_secret = api_keys.get("convertapi")
        
        if not api_secret:
            raise ValueError("Missing ConvertAPI secret in configuration. Please configure it via the menu.")

    def process_file(self, input_file: Path, output_dir: Path):
        """
        Processes a single PPTX file using consolidated conversion processor.
        Converts to PDF, PNG, or WEBP with proper sequential naming.
        """
        try:
            # Check for interruption
            if self.stop_flag.is_set():
                raise InterruptedError("Processing stopped by user")
            
            output_format = self.output_format.get()
            
            # Determine output path based on format
            if output_format == 'pdf':
                output_file = output_dir / f"{input_file.stem}.pdf"
            else:
                # For image formats, the processor will handle multiple output files
                output_file = output_dir / f"{input_file.stem}_slide_01.{output_format}"
            
            # Create conversion processor with GUI-specific progress reporter
            progress_reporter = ProgressReporter(callback=lambda msg: (
                self.send_progress_update(msg) if not self.stop_flag.is_set() 
                else (_ for _ in ()).throw(InterruptedError("Processing stopped by user"))
            ))
            
            processor = create_conversion_processor(
                self.service_manager,
                progress_reporter=progress_reporter,
                config=ProcessorConfig(
                    skip_existing=self.check_output_exists.get(),
                    allowed_extensions=self.supported_extensions,
                    output_formats=['pdf', 'png', 'webp'],
                    max_file_size_mb=25.0
                )
            )
            
            # Process the file using consolidated processor
            result = processor.process_file(
                input_file,
                output_file,
                output_format=output_format
            )
            
            if result.success:
                self.send_progress_update(f"Successfully converted: {input_file.name}")
                return True
            elif result.skipped:
                # Skip message already sent by processor
                return True
            else:
                self.send_progress_update(f"Failed to convert: {input_file.name} - {result.message}")
                return False

        except InterruptedError:
            raise
        except Exception as e:
            error_msg = f"Failed to convert {input_file.name}: {str(e)}"
            self.send_progress_update(f"ERROR: {error_msg}")
            logging.error(error_msg, exc_info=True)
            return False

    def after_processing(self):
        """Cleanup after processing batch."""
        self.send_progress_update("PPTX conversion batch finished.")