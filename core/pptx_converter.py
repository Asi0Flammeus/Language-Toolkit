"""
PPTX to PDF/PNG/WEBP Conversion Core Module

This module provides PowerPoint to PDF, PNG, and WEBP conversion functionality using ConvertAPI.
It can convert PPTX presentations to high-quality PDF documents or individual PNG/WEBP images.

Usage Examples:
    GUI: Integrated with file browsers, format selection, and progress indicators
    API: Used via REST endpoints for document conversion services
    CLI: Command-line presentation conversion for batch processing

Features:
    - ConvertAPI integration for reliable conversion
    - PDF conversion (single document output)
    - PNG conversion (individual slide images)
    - WEBP conversion (PNG to WEBP with optimization)
    - High-quality output preservation
    - Progress callback support for user feedback
    - Comprehensive error handling and validation
    - Batch processing capabilities

Output Formats:
    - PDF: Single document with all slides
    - PNG: Individual image files per slide
    - WEBP: Individual optimized image files per slide
    - Maintains original slide dimensions and quality
    - Preserves fonts and formatting

Conversion Quality:
    - High-resolution output
    - Vector graphics preservation (PDF)
    - WEBP optimization with quality control
    - Consistent rendering across platforms
    - Professional document quality
"""

import logging
import convertapi
from pathlib import Path
from typing import Optional, Callable, List
from PIL import Image

logger = logging.getLogger(__name__)

class PPTXConverterCore:
    """
    Core PPTX to PDF/PNG/WEBP conversion functionality using ConvertAPI.
    
    This class provides reliable PowerPoint conversion capabilities with
    support for PDF, PNG, and WEBP output formats. It maintains high quality
    and preserves original presentation formatting.
    
    Key Features:
        - Reliable conversion via ConvertAPI
        - Multiple output format support (PDF, PNG, WEBP)
        - High-quality output preservation
        - WEBP optimization with quality control
        - Progress tracking with callback support
        - Batch processing capabilities
        - Comprehensive error handling
        - Professional document quality
    
    Requirements:
        - ConvertAPI key and subscription
        - convertapi Python library
        - PIL/Pillow for WEBP conversion
        - Valid PPTX input files
    
    Example Usage:
        converter = PPTXConverterCore(api_key="your-convertapi-key")
        
        # Convert to PDF
        success = converter.convert_pptx_to_pdf(
            input_path=Path("presentation.pptx"),
            output_path=Path("document.pdf")
        )
        
        # Convert to PNG images
        png_files = converter.convert_pptx_to_png(
            input_path=Path("presentation.pptx"),
            output_dir=Path("images/")
        )
        
        # Convert to WEBP images
        webp_files = converter.convert_pptx_to_webp(
            input_path=Path("presentation.pptx"),
            output_dir=Path("images/")
        )
    """
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize PPTX converter core.
        
        Args:
            api_key: ConvertAPI key
            progress_callback: Optional callback function for progress updates
        """
        self.api_key = api_key
        self.progress_callback = progress_callback or (lambda x: None)
        self._init_convert_api()
    
    def _init_convert_api(self):
        """Initialize ConvertAPI."""
        if not self.api_key:
            raise ValueError("ConvertAPI key is required")
        
        try:
            convertapi.api_secret = self.api_key
            self.progress_callback("ConvertAPI initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize ConvertAPI: {e}")
    
    def convert_pptx_to_pdf(self, input_path: Path, output_path: Path) -> bool:
        """
        Convert PPTX file to PDF.
        
        Args:
            input_path: Path to input PPTX file
            output_path: Path to output PDF file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.progress_callback(f"Converting PPTX to PDF: {input_path}")
            
            # Validate input file
            if not self.validate_pptx_file(input_path):
                raise ValueError(f"Invalid PPTX file: {input_path}")
            
            # Convert using ConvertAPI
            result = convertapi.convert('pdf', {
                'File': str(input_path)
            }, from_format='pptx')
            
            # Save result
            self.progress_callback(f"Saving PDF to: {output_path}")
            result.file.save(str(output_path))
            
            self.progress_callback("PPTX to PDF conversion completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to convert PPTX to PDF: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def convert_pptx_to_png(self, input_path: Path, output_dir: Path) -> List[str]:
        """
        Convert PPTX file to PNG images (one per slide).
        
        Args:
            input_path: Path to input PPTX file
            output_dir: Directory to save PNG files
            
        Returns:
            List of paths to generated PNG files
        """
        try:
            self.progress_callback(f"Converting PPTX to PNG: {input_path}")
            
            # Validate input file
            if not self.validate_pptx_file(input_path):
                raise ValueError(f"Invalid PPTX file: {input_path}")
            
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Convert using ConvertAPI
            result = convertapi.convert('png', {
                'File': str(input_path)
            }, from_format='pptx')
            
            # Save all PNG files
            png_files = []
            base_name = input_path.stem
            
            self.progress_callback("Saving PNG files...")
            
            if hasattr(result, 'files') and result.files:
                # Multiple files (slides)
                for i, file_result in enumerate(result.files, 1):
                    png_path = output_dir / f"{base_name}_slide_{i:02d}.png"
                    file_result.save(str(png_path))
                    png_files.append(str(png_path))
                    self.progress_callback(f"Saved slide {i} as PNG")
            else:
                # Single file
                png_path = output_dir / f"{base_name}.png"
                result.file.save(str(png_path))
                png_files.append(str(png_path))
                self.progress_callback("Saved PNG file")
            
            self.progress_callback(f"PPTX to PNG conversion completed successfully. Generated {len(png_files)} files")
            return png_files
            
        except Exception as e:
            error_msg = f"Failed to convert PPTX to PNG: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return []
    
    def validate_pptx_file(self, file_path: Path) -> bool:
        """Validate that the file is a valid PPTX file."""
        if not file_path.exists():
            return False
        
        if file_path.suffix.lower() != '.pptx':
            return False
        
        # Basic file size check (PPTX files should be larger than empty ZIP)
        return file_path.stat().st_size > 1000
    
    def convert_pptx_to_webp(self, input_path: Path, output_dir: Path, quality: int = 85) -> List[str]:
        """
        Convert PPTX file to WEBP images (one per slide).
        
        Args:
            input_path: Path to input PPTX file
            output_dir: Directory to save WEBP files
            quality: WEBP quality (0-100, default 85)
            
        Returns:
            List of paths to generated WEBP files
        """
        try:
            self.progress_callback(f"Converting PPTX to WEBP: {input_path}")
            
            # Validate input file
            if not self.validate_pptx_file(input_path):
                raise ValueError(f"Invalid PPTX file: {input_path}")
            
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # First convert to PNG using existing method
            self.progress_callback("Converting to PNG first...")
            png_files = self.convert_pptx_to_png(input_path, output_dir)
            
            if not png_files:
                raise RuntimeError("Failed to convert PPTX to PNG")
            
            # Convert each PNG to WEBP
            webp_files = []
            base_name = input_path.stem
            
            self.progress_callback("Converting PNG files to WEBP...")
            
            for i, png_path in enumerate(png_files):
                png_file = Path(png_path)
                webp_name = f"{base_name}_{i:02d}.webp"
                webp_path = output_dir / webp_name
                
                # Convert PNG to WEBP using PIL
                self.progress_callback(f"Converting slide {i+1} to WEBP...")
                with Image.open(png_file) as img:
                    img.save(webp_path, 'WEBP', quality=quality, method=6)
                
                # Remove the temporary PNG file
                png_file.unlink()
                
                webp_files.append(str(webp_path))
                self.progress_callback(f"Saved slide {i+1} as WEBP")
            
            self.progress_callback(f"PPTX to WEBP conversion completed successfully. Generated {len(webp_files)} files")
            return webp_files
            
        except Exception as e:
            error_msg = f"Failed to convert PPTX to WEBP: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return []
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported output formats."""
        return ['pdf', 'png', 'webp']