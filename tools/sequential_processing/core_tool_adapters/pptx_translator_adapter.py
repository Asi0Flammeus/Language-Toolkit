"""PPTX Translation Adapter for Sequential Processing."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Callable

from . import CoreToolAdapter
from core.pptx_translation import PPTXTranslationCore

logger = logging.getLogger(__name__)


class PPTXTranslatorAdapter(CoreToolAdapter):
    """Adapter for PPTX Translation Core Tool."""
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize PPTX translator adapter.
        
        Args:
            api_key: DeepL API key
            progress_callback: Optional callback for progress updates
        """
        super().__init__(progress_callback)
        self.api_key = api_key
        self.tool = None
    
    def _initialize_tool(self):
        """Initialize the core tool if not already done."""
        if not self.tool:
            self.tool = PPTXTranslationCore(
                api_key=self.api_key,
                progress_callback=self.progress_callback
            )
    
    def process(self, input_path: Path, output_path: Path, params: Dict[str, Any]) -> bool:
        """
        Translate a PPTX file.
        
        Args:
            input_path: Path to input PPTX file
            output_path: Path to output location (directory or file)
            params: Must include 'source_lang' and 'target_lang'
            
        Returns:
            True if successful, False otherwise
        """
        self._initialize_tool()
        
        source_lang = params.get('source_lang', 'en')
        target_lang = params.get('target_lang', 'es')
        
        # If output_path is a directory, create output file path
        if output_path.is_dir():
            output_file = output_path / f"{input_path.stem}_{target_lang}.pptx"
        else:
            output_file = output_path
            output_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self.report_progress(f"Translating PPTX: {input_path.name} ({source_lang} → {target_lang})")
            
            success = self.tool.translate_pptx(
                input_path=input_path,
                output_path=output_file,
                source_lang=source_lang,
                target_lang=target_lang
            )
            
            if success:
                self.report_progress(f"✓ Translated PPTX saved to: {output_file}")
            else:
                self.report_progress(f"✗ Failed to translate PPTX: {input_path.name}")
                
            return success
            
        except Exception as e:
            logger.exception(f"Error translating PPTX {input_path}: {str(e)}")
            self.report_progress(f"✗ Error translating PPTX: {str(e)}")
            return False
    
    def validate_input(self, input_path: Path) -> bool:
        """
        Validate if the input is a PPTX file.
        
        Args:
            input_path: Path to validate
            
        Returns:
            True if input is a PPTX file
        """
        return input_path.suffix.lower() == '.pptx' and input_path.exists()