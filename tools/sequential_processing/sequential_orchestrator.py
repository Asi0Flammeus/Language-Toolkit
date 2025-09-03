"""Sequential Processing Orchestrator - Main coordinator for multi-language workflows."""

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

from .core_tool_adapters.pptx_translator_adapter import PPTXTranslatorAdapter
from .core_tool_adapters.pptx_exporter_adapter import PPTXExporterAdapter
from .core_tool_adapters.text_translator_adapter import TextTranslatorAdapter
from .core_tool_adapters.tts_adapter import TTSAdapter
from .core_tool_adapters.video_merger_adapter import VideoMergerAdapter
from .utils.folder_structure_manager import FolderStructureManager
from .utils.processing_pipeline import ProcessingPipeline, ProcessingResult
from .utils.progress_aggregator import ProgressAggregator
from .utils.error_handler import ErrorHandler, ErrorCategory

logger = logging.getLogger(__name__)


class SequentialOrchestrator:
    """
    Main orchestrator for sequential processing workflows.
    
    Coordinates multiple core tools to process files through translation,
    export, audio generation, and video creation workflows while preserving
    folder structure.
    """
    
    def __init__(self, config: Dict[str, Any], 
                 progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize the sequential orchestrator.
        
        Args:
            config: Configuration dictionary with API keys
            progress_callback: Optional callback for progress updates
        """
        self.config = config
        self.progress_callback = progress_callback or (lambda x: None)
        self.stop_flag = threading.Event()
        
        # Initialize components
        self.folder_manager = FolderStructureManager()
        self.progress_aggregator = ProgressAggregator(progress_callback)
        self.error_handler = ErrorHandler(progress_callback)
        
        # Initialize adapters
        self.adapters = self._initialize_adapters()
        
        # Initialize pipeline
        self.pipeline = ProcessingPipeline(self.adapters, progress_callback)
        self.pipeline.set_stop_flag(self.stop_flag)
    
    def _initialize_adapters(self) -> Dict[str, Any]:
        """Initialize all core tool adapters."""
        adapters = {}
        
        # PPTX Translation adapter
        if 'deepl_api_key' in self.config:
            adapters['pptx_translator'] = PPTXTranslatorAdapter(
                api_key=self.config['deepl_api_key'],
                progress_callback=self.progress_callback
            )
            adapters['text_translator'] = TextTranslatorAdapter(
                api_key=self.config['deepl_api_key'],
                progress_callback=self.progress_callback
            )
        
        # PPTX Export adapter
        if 'convertapi_key' in self.config:
            adapters['pptx_exporter'] = PPTXExporterAdapter(
                api_key=self.config['convertapi_key'],
                progress_callback=self.progress_callback
            )
        
        # TTS adapter
        if 'elevenlabs_api_key' in self.config:
            adapters['tts'] = TTSAdapter(
                api_key=self.config['elevenlabs_api_key'],
                progress_callback=self.progress_callback
            )
        
        # Video merger adapter (no API key required)
        adapters['video_merger'] = VideoMergerAdapter(
            progress_callback=self.progress_callback
        )
        
        return adapters
    
    def process_folder(self, input_path: Path, output_path: Path,
                      source_lang: str, target_langs: List[str],
                      use_intro: bool = False, skip_existing: bool = True) -> bool:
        """
        Process a folder through all selected languages.
        
        Args:
            input_path: Path to input folder
            output_path: Path to output folder
            source_lang: Source language code
            target_langs: List of target language codes
            use_intro: Whether to add intro video to generated videos
            skip_existing: Whether to skip files that already exist
            
        Returns:
            True if successful, False if interrupted or failed
        """
        try:
            # Clear stop flag
            self.stop_flag.clear()
            
            # Scan input folder structure
            self.progress_callback("📂 Scanning input folder structure...")
            folder_map = self.folder_manager.scan_input(input_path)
            
            if not folder_map:
                self.progress_callback("⚠️ No files found in input folder")
                return False
            
            # Get folder statistics
            stats = self.folder_manager.get_folder_stats()
            self.progress_callback(
                f"📊 Found: {stats['total_folders']} folders, "
                f"{stats['pptx_files']} PPTX files, "
                f"{stats['txt_files']} text files"
            )
            
            # Initialize progress tracking
            self.progress_aggregator.initialize(target_langs, len(folder_map))
            
            # Process each target language sequentially
            all_results = []
            
            for target_lang in target_langs:
                if self.stop_flag.is_set():
                    self.progress_callback("⏹️ Processing stopped by user")
                    break
                
                # Start language processing
                self.progress_aggregator.start_language(target_lang)
                
                # Create output structure for this language
                lang_output_path = self.folder_manager.create_output_structure(
                    input_path, output_path, target_lang
                )
                
                # Process each subfolder
                folder_results = []
                
                for rel_path, folder_info in folder_map.items():
                    if self.stop_flag.is_set():
                        break
                    
                    # Start folder processing
                    self.progress_aggregator.start_folder(rel_path)
                    
                    # Process the subfolder
                    result = self.pipeline.process_subfolder(
                        folder_info['full_path'],
                        lang_output_path,
                        source_lang,
                        target_lang,
                        rel_path,
                        use_intro=use_intro,
                        skip_existing=skip_existing
                    )
                    
                    folder_results.append(result)
                    
                    # Complete folder
                    success = len(result.errors) == 0
                    error_msg = result.errors[0] if result.errors else None
                    self.progress_aggregator.complete_folder(success, error_msg)
                
                all_results.extend(folder_results)
            
            # Generate final summary
            summary = self.pipeline.get_summary(all_results)
            self.progress_callback(summary)
            
            # Add error summary
            error_summary = self.error_handler.get_error_summary()
            self.progress_callback(error_summary)
            
            # Generate final report
            report = self.progress_aggregator.get_final_report()
            self.progress_callback(report)
            
            # Export error log if there were errors
            if self.error_handler.errors:
                error_log_path = output_path / "error_log.txt"
                self.error_handler.export_error_log(str(error_log_path))
            
            return not self.stop_flag.is_set()
            
        except Exception as e:
            self.error_handler.handle_error(
                e, 
                "orchestrated processing",
                ErrorCategory.PROCESSING_ERROR
            )
            logger.exception(f"Error during orchestrated processing: {str(e)}")
            self.progress_callback(f"❌ Critical error: {str(e)}")
            return False
    
    def stop_processing(self):
        """Stop the current processing operation."""
        self.stop_flag.set()
        self.progress_callback("🛑 Stopping processing...")
    
    def validate_configuration(self) -> Dict[str, bool]:
        """
        Validate that all required API keys are configured.
        
        Returns:
            Dictionary of tool names and their availability
        """
        availability = {
            'pptx_translation': 'deepl_api_key' in self.config,
            'pptx_export': 'convertapi_key' in self.config,
            'text_translation': 'deepl_api_key' in self.config,
            'text_to_speech': 'elevenlabs_api_key' in self.config,
            'video_merger': True  # Always available
        }
        
        return availability
    
    def get_supported_languages(self) -> Dict[str, Dict[str, str]]:
        """
        Get supported languages for translation.
        
        Returns:
            Dictionary with source and target language options
        """
        # This should ideally come from the core tools
        # For now, return a standard set
        languages = {
            'source_languages': {
                'en': 'English',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'ru': 'Russian',
                'zh': 'Chinese',
                'ja': 'Japanese',
                'ko': 'Korean'
            },
            'target_languages': {
                'en': 'English',
                'es': 'Spanish',
                'fr': 'French',
                'de': 'German',
                'it': 'Italian',
                'pt': 'Portuguese',
                'ru': 'Russian',
                'zh': 'Chinese',
                'ja': 'Japanese',
                'ko': 'Korean',
                'ar': 'Arabic',
                'hi': 'Hindi',
                'tr': 'Turkish',
                'pl': 'Polish',
                'nl': 'Dutch',
                'sv': 'Swedish'
            }
        }
        
        return languages