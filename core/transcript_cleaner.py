"""
Transcript Cleaner Core Module

This module provides functionality to clean and tighten raw audio transcripts using Claude AI.
It removes filler words, fixes grammar, and produces polished transcripts suitable for presentation.

Usage Examples:
    GUI: Clean raw transcripts from audio recordings 
    API: Process transcript cleaning via REST endpoints
    CLI: Batch clean transcript files from command line
    
Features:
    - Claude Sonnet API integration for intelligent transcript cleaning
    - Removes filler words (um, uh, like, you know)
    - Fixes grammatical errors and incomplete sentences
    - Maintains speaker's voice and technical accuracy
    - Recursive folder processing for batch operations
    - Preserves original files with "-ai-cleaned.txt" suffix for outputs
"""

import logging
import os
from pathlib import Path
from typing import Optional, Callable, List
import anthropic

logger = logging.getLogger(__name__)

class TranscriptCleanerCore:
    """
    Core transcript cleaning functionality using Claude AI.
    
    This class provides intelligent transcript cleaning capabilities
    using Claude Sonnet to remove filler words, fix grammar, and
    produce presentation-ready transcripts from raw recordings.
    
    Key Features:
        - Claude Sonnet 3.5 integration for AI-powered cleaning
        - Preserves speaker voice and technical accuracy
        - Batch processing with recursive folder support
        - Progress tracking with callback support
        - Original file preservation with clear naming
        - Comprehensive error handling
    
    Requirements:
        - Anthropic API key
        - anthropic Python library
        - Valid text input files
    
    Example Usage:
        cleaner = TranscriptCleanerCore(api_key="your-anthropic-key")
        success = cleaner.clean_transcript(
            input_path=Path("raw_transcript.txt"),
            output_path=Path("cleaned_transcript.txt")
        )
    """
    
    # System prompt for Claude
    SYSTEM_PROMPT = """You are a transcript editor. Your task is to clean and tighten audio transcripts from raw recordings into polished versions suitable for online presentation. You must output ONLY the cleaned transcript text without any additional commentary, explanations, or formatting marks."""
    
    # User prompt template 
    USER_PROMPT_TEMPLATE = """Rewrite the following audio transcript from raw live recording footage into a trimmed and tightened version for online presentation. Output only the rewritten text.

Requirements:
- Maintain close fidelity to the original content and speaker's voice
- Trim unnecessary content while keeping all key information
- Tighten sentences for clarity and flow
- Remove filler words (um, uh, you know, like)
- Eliminate redundant repetitions and false starts
- Fix grammatical errors and incomplete sentences
- Preserve all technical terms and important details
- Keep the conversational tone where appropriate
- Ensure each slide's content remains self-contained

Input format: One text segment per PowerPoint slide
Output format: Cleaned, trimmed and tightened transcript only, no additional commentary

Transcript to clean:
{transcript}"""
    
    def __init__(self, api_key: str, progress_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize transcript cleaner core.
        
        Args:
            api_key: Anthropic API key
            progress_callback: Optional callback function for progress updates
        """
        self.api_key = api_key
        self.progress_callback = progress_callback or (lambda x: None)
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Anthropic client."""
        if not self.api_key:
            raise ValueError("Anthropic API key is required")
        
        try:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.progress_callback("Anthropic client initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Anthropic client: {e}")
    
    def clean_transcript_text(self, text: str) -> str:
        """
        Clean transcript text using Claude AI.
        
        Args:
            text: Raw transcript text to clean
            
        Returns:
            Cleaned transcript text
            
        Raises:
            Exception: If API call fails
        """
        try:
            self.progress_callback("Sending transcript to Claude for cleaning...")
            
            # Create the message for Claude
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                temperature=0.3,
                system=self.SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": self.USER_PROMPT_TEMPLATE.format(transcript=text)
                    }
                ]
            )
            
            # Extract the cleaned text from response
            cleaned_text = message.content[0].text
            
            self.progress_callback("Transcript cleaning completed")
            return cleaned_text
            
        except Exception as e:
            error_msg = f"Failed to clean transcript: {str(e)}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            raise
    
    def clean_transcript_file(self, input_path: Path, output_path: Optional[Path] = None) -> bool:
        """
        Clean a transcript file.
        
        Args:
            input_path: Path to input transcript file
            output_path: Optional path for output file (defaults to input_path with -ai-cleaned.txt suffix)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate input file
            if not input_path.exists():
                error_msg = f"Input file not found: {input_path}"
                logger.error(error_msg)
                self.progress_callback(f"Error: {error_msg}")
                return False
            
            # Generate output path if not provided
            if output_path is None:
                output_path = input_path.parent / f"{input_path.stem}-ai-cleaned.txt"
            
            self.progress_callback(f"Processing: {input_path.name}")
            
            # Read input transcript
            with open(input_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
            
            if not raw_text.strip():
                self.progress_callback(f"Skipping empty file: {input_path.name}")
                return False
            
            # Clean the transcript
            cleaned_text = self.clean_transcript_text(raw_text)
            
            # Save cleaned transcript
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)
            
            self.progress_callback(f"Saved cleaned transcript: {output_path.name}")
            return True
            
        except Exception as e:
            error_msg = f"Failed to process file {input_path}: {str(e)}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return False
    
    def clean_folder(self, folder_path: Path, recursive: bool = False) -> List[Path]:
        """
        Clean all transcript files in a folder.
        
        Args:
            folder_path: Path to folder containing transcript files
            recursive: Whether to process subfolders recursively
            
        Returns:
            List of successfully processed file paths
        """
        processed_files = []
        
        if not folder_path.exists() or not folder_path.is_dir():
            error_msg = f"Invalid folder path: {folder_path}"
            logger.error(error_msg)
            self.progress_callback(f"Error: {error_msg}")
            return processed_files
        
        # Get all .txt files (excluding already cleaned ones)
        if recursive:
            txt_files = [f for f in folder_path.rglob("*.txt") 
                        if not f.name.endswith("-ai-cleaned.txt")]
        else:
            txt_files = [f for f in folder_path.glob("*.txt") 
                        if not f.name.endswith("-ai-cleaned.txt")]
        
        total_files = len(txt_files)
        
        if total_files == 0:
            self.progress_callback("No transcript files found to process")
            return processed_files
        
        self.progress_callback(f"Found {total_files} transcript files to clean")
        
        for i, file_path in enumerate(txt_files, 1):
            self.progress_callback(f"Processing file {i}/{total_files}: {file_path.name}")
            
            if self.clean_transcript_file(file_path):
                processed_files.append(file_path)
            
        self.progress_callback(f"Completed: {len(processed_files)}/{total_files} files cleaned successfully")
        return processed_files