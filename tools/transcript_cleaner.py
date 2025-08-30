"""Transcript cleaning tool using Claude AI."""

from pathlib import Path

from ui.base_tool import ToolBase
from core.transcript_cleaner import TranscriptCleanerCore


class TranscriptCleanerTool(ToolBase):
    """Clean and tighten raw transcripts using Claude AI"""
    
    def __init__(self, master, config_manager, progress_queue):
        super().__init__(master, config_manager, progress_queue)
        
        self.supported_extensions = {'.txt'}
        self.title = "Clean Raw Transcript"
        self.description = "Clean and tighten raw audio transcripts"
        
        # Get Anthropic API key from config
        api_keys = config_manager.get_api_keys()
        api_key = api_keys.get('anthropic', '')
        
        if api_key:
            self.api_key = api_key
            self.tool_core = TranscriptCleanerCore(
                api_key=api_key,
                progress_callback=self.update_progress
            )
        else:
            self.api_key = None
            self.tool_core = None
    
    def update_progress(self, message):
        """Update progress display with a message."""
        self.send_progress_update(message)
    
    def process_file(self, input_path, output_dir):
        """Process a single transcript file"""
        if not self.tool_core:
            raise ValueError("Anthropic API key not configured. Please configure API keys first.")
        
        try:
            input_p = Path(input_path)
            
            # Create output file path with -ai-cleaned.txt suffix in the output directory
            output_p = Path(output_dir) / f"{input_p.stem}-ai-cleaned.txt"
            
            # Clean the transcript
            success = self.tool_core.clean_transcript_file(input_p, output_p)
            
            if success:
                self.update_progress(f"✓ Cleaned transcript saved: {output_p.name}")
                return str(output_p)
            else:
                raise Exception("Failed to clean transcript")
                
        except Exception as e:
            error_msg = f"Error cleaning transcript: {str(e)}"
            self.update_progress(error_msg)
            raise Exception(error_msg)
    
    def process_folder(self, folder_path, output_path=None, recursive=False):
        """Process all transcript files in a folder"""
        if not self.tool_core:
            raise ValueError("Anthropic API key not configured. Please configure API keys first.")
        
        try:
            folder_p = Path(folder_path)
            output_p = Path(output_path) if output_path else None
            processed_files = self.tool_core.clean_folder(folder_p, recursive=recursive, output_path=output_p)
            
            if processed_files:
                self.update_progress(f"✓ Successfully cleaned {len(processed_files)} transcripts")
                return processed_files
            else:
                self.update_progress("No transcripts were cleaned")
                return []
                
        except Exception as e:
            error_msg = f"Error processing folder: {str(e)}"
            self.update_progress(error_msg)
            raise Exception(error_msg)