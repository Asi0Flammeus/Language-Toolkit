
import subprocess
import logging
import sys
from pathlib import Path

sys.path.append("../")
from tools.tool_base import ToolBase  
from config.config_manager import ConfigManager 

class PPTXToPNGTool(ToolBase):
    """Converts PPTX files to PNG images (slides by slides) using LibreOffice and ImageMagick."""

    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        self.adobe_api_key = config_manager.get_api_keys().get("adobe", None)  # Example

    def process_file(self, input_file: Path, output_dir: Path = None):
        """Converts a single PPTX file to PNG images."""
        if input_file.suffix.lower() != ".pptx":
            self.send_progress_update(f"Skipping non-PPTX file: {input_file}")
            return

        try:
            self.send_progress_update(f"Converting {input_file.name} to PNG...")
            # Build the command
            command = [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(input_file)
            ]

            # Execute the command
            result = subprocess.run(command, capture_output=True, text=True, check=True)

            # Extract PDF file path from output directory and input file name
            pdf_file = output_dir / input_file.with_suffix(".pdf").name

            # Convert PDF to a series of PNGs with ImageMagick
            convert_command = [
                "magick",
                "convert",
                "-density",
                "300",  # You can adjust the DPI here
                str(pdf_file),
                str(output_dir / f"{input_file.stem}-%03d.png")  # output to png files in the out_dir
            ]

            # Execute the conversion command
            result = subprocess.run(convert_command, capture_output=True, text=True, check=True)
            self.send_progress_update(f"Successfully converted {input_file.name} to PNG images in {output_dir}")

        except subprocess.CalledProcessError as e:
            error_message = f"Error converting {input_file.name}: {e.stderr}"
            self.send_progress_update(error_message)
            logging.error(error_message)
        except Exception as e:
            error_message = f"Unexpected error processing {input_file.name}: {e}"
            self.send_progress_update(error_message)
            logging.exception(error_message)

