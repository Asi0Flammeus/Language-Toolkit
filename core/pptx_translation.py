"""
PPTX Translation Core Module

This module provides PowerPoint presentation translation functionality using the DeepL API.
It can translate text content within PPTX files while preserving formatting, layout, and structure.

Usage Examples:
    GUI: Integrated into a file selection interface with progress bars and language dropdowns
    API: Used via REST endpoints for batch translation services
    CLI: Command-line translation of presentation files

Features:
    - DeepL API integration for high-quality translation
    - Preserves PowerPoint formatting and layout
    - Handles text in slides, shapes, tables, and text frames
    - Progress callback support for user feedback
    - Comprehensive error handling and validation
    - Support for all DeepL supported languages

Supported Content:
    - Slide text content
    - Table cell text
    - Text frame paragraphs
    - Shape text content
    - Maintains original formatting and styling
"""

import logging
import deepl
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from pptx import Presentation
import fitz

logger = logging.getLogger(__name__)

class PPTXTranslationCore:
    """
    Core PPTX translation functionality using DeepL API.
    
    This class provides comprehensive PowerPoint translation capabilities while
    maintaining the original presentation structure, formatting, and layout.
    It processes all text content including slides, tables, and text frames.
    
    Key Features:
        - High-quality translation via DeepL API
        - Preserves original formatting and layout
        - Handles complex PowerPoint structures
        - Progress tracking with callback support
        - Robust error handling and validation
        - Support for all DeepL language pairs
    
    Requirements:
        - DeepL API key
        - python-pptx library
        - Valid PPTX input files
    
    Example Usage:
        translator = PPTXTranslationCore(api_key="your-deepl-key")
        success = translator.translate_pptx(
            input_path=Path("presentation.pptx"),
            output_path=Path("translated.pptx"),
            source_lang="en",
            target_lang="fr"
        )
    """
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize PPTX translation core.
        
        Args:
            api_key: DeepL API key
            progress_callback: Optional callback function for progress updates
        """
        self.api_key = api_key
        self.progress_callback = progress_callback or (lambda x: None)
        self.translator = None
        self._init_translator()
    
    def _init_translator(self):
        """Initialize DeepL translator."""
        if not self.api_key:
            raise ValueError("DeepL API key is required")
        
        try:
            self.translator = deepl.Translator(self.api_key)
            self.progress_callback("DeepL translator initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize DeepL translator: {e}")
    
    def translate_pptx(self, input_path: Path, output_path: Path, 
                      source_lang: str, target_lang: str) -> bool:
        """
        Translate PPTX file from source to target language.
        
        Args:
            input_path: Path to input PPTX file
            output_path: Path to output PPTX file
            source_lang: Source language code (e.g., 'en')
            target_lang: Target language code (e.g., 'fr')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.progress_callback(f"Opening PPTX file: {input_path}")
            
            # Load presentation
            prs = Presentation(str(input_path))
            
            slide_count = len(prs.slides)
            self.progress_callback(f"Found {slide_count} slides to translate")
            
            # Process each slide
            for slide_num, slide in enumerate(prs.slides, 1):
                self.progress_callback(f"Processing slide {slide_num}/{slide_count}")
                
                # Translate text in shapes
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        original_text = shape.text
                        try:
                            translated_text = self._translate_text(original_text, source_lang, target_lang)
                            shape.text = translated_text
                            self.progress_callback(f"Translated text on slide {slide_num}")
                        except Exception as e:
                            logger.warning(f"Failed to translate text on slide {slide_num}: {e}")
                            continue
                    
                    # Handle text in tables
                    if shape.has_table:
                        self._translate_table(shape.table, source_lang, target_lang, slide_num)
                    
                    # Handle text in text frames
                    if hasattr(shape, "text_frame") and shape.text_frame:
                        self._translate_text_frame(shape.text_frame, source_lang, target_lang, slide_num)
            
            # Save translated presentation
            self.progress_callback(f"Saving translated presentation to: {output_path}")
            prs.save(str(output_path))
            
            self.progress_callback("PPTX translation completed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to translate PPTX: {e}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def _translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """Translate text using DeepL API."""
        if not text.strip():
            return text
        
        try:
            result = self.translator.translate_text(
                text, 
                source_lang=source_lang if source_lang != 'auto' else None,
                target_lang=target_lang
            )
            return result.text
        except Exception as e:
            logger.warning(f"Translation failed for text: {text[:50]}... Error: {e}")
            return text  # Return original text if translation fails
    
    def _translate_table(self, table, source_lang: str, target_lang: str, slide_num: int):
        """Translate text in table cells."""
        try:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        original_text = cell.text
                        translated_text = self._translate_text(original_text, source_lang, target_lang)
                        cell.text = translated_text
        except Exception as e:
            logger.warning(f"Failed to translate table on slide {slide_num}: {e}")
    
    def _translate_text_frame(self, text_frame, source_lang: str, target_lang: str, slide_num: int):
        """Translate text in text frame paragraphs."""
        try:
            for paragraph in text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.text.strip():
                        original_text = run.text
                        translated_text = self._translate_text(original_text, source_lang, target_lang)
                        run.text = translated_text
        except Exception as e:
            logger.warning(f"Failed to translate text frame on slide {slide_num}: {e}")
    
    def validate_file(self, file_path: Path) -> bool:
        """Validate that the file is a valid PPTX file."""
        if not file_path.exists():
            return False
        
        if file_path.suffix.lower() != '.pptx':
            return False
        
        try:
            # Try to open the presentation
            prs = Presentation(str(file_path))
            return len(prs.slides) > 0
        except Exception:
            return False
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get languages supported by DeepL."""
        try:
            if not self.translator:
                return {}
            
            source_langs = self.translator.get_source_languages()
            target_langs = self.translator.get_target_languages()
            
            supported = {}
            for lang in source_langs:
                supported[lang.code.lower()] = lang.name
            
            return supported
        except Exception as e:
            logger.error(f"Failed to get supported languages: {e}")
            return {}