"""PPTX Export to PNG Adapter for Sequential Processing."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Callable, List

from . import CoreToolAdapter
from core.pptx_converter import PPTXConverterCore

logger = logging.getLogger(__name__)


class PPTXExporterAdapter(CoreToolAdapter):
    """Adapter for PPTX to PNG Export Core Tool."""
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize PPTX exporter adapter.
        
        Args:
            api_key: ConvertAPI key
            progress_callback: Optional callback for progress updates
        """
        super().__init__(progress_callback)
        self.api_key = api_key
        self.tool = None
    
    def _initialize_tool(self):
        """Initialize the core tool if not already done."""
        if not self.tool:
            self.tool = PPTXConverterCore(
                api_key=self.api_key,
                progress_callback=self.progress_callback
            )
    
    def process(self, input_path: Path, output_path: Path, params: Dict[str, Any]) -> List[Path]:
        """
        Export PPTX slides to PNG images.
        
        Args:
            input_path: Path to input PPTX file
            output_path: Path to output directory for PNG files (same level as PPTX)
            params: Additional parameters including:
                - group_elements: If True, crop PNG to element bounds (default: False)
            
        Returns:
            List of generated PNG file paths
        """
        self._initialize_tool()
        
        # Use the parent directory of the PPTX file for PNG output (same level)
        # output_path here should already be the correct directory
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Extract group_elements parameter, default to False for backward compatibility
        group_elements = params.get('group_elements', False) if params else False
        
        try:
            self.report_progress(f"Exporting PPTX to PNG: {input_path.name}")
            if group_elements:
                self.report_progress("Element grouping enabled - will crop to content bounds")
            
            png_files = self.tool.convert_pptx_to_png(
                input_path=input_path,
                output_dir=output_path,  # PNG files go in same directory as PPTX
                group_elements=group_elements
            )
            
            if png_files:
                # Convert string paths to Path objects
                png_paths = [Path(png_file) for png_file in png_files]
                self.report_progress(f"✓ Exported {len(png_paths)} PNG files from: {input_path.name}")
                return png_paths
            else:
                self.report_progress(f"✗ Failed to export PNG from: {input_path.name}")
                return []
                
        except Exception as e:
            logger.exception(f"Error exporting PPTX to PNG {input_path}: {str(e)}")
            self.report_progress(f"✗ Error exporting PPTX to PNG: {str(e)}")
            return []
    
    def validate_input(self, input_path: Path) -> bool:
        """
        Validate if the input is a PPTX file.
        
        Args:
            input_path: Path to validate
            
        Returns:
            True if input is a PPTX file
        """
        return input_path.suffix.lower() == '.pptx' and input_path.exists()