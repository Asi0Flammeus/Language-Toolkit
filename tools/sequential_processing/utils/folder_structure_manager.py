"""Folder Structure Manager for Sequential Processing."""

import logging
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


class FolderStructureManager:
    """Manages folder structure preservation for sequential processing."""
    
    def __init__(self):
        """Initialize the folder structure manager."""
        self.folder_map = {}
        self.supported_extensions = {
            'pptx': ['.pptx'],
            'text': ['.txt'],
            'image': ['.png', '.jpg', '.jpeg', '.bmp'],
            'audio': ['.mp3', '.wav', '.m4a'],
            'video': ['.mp4', '.avi', '.mov']
        }
    
    def scan_input(self, input_path: Path) -> Dict[str, Dict]:
        """
        Scan input directory and create a folder map.
        
        Args:
            input_path: Root input directory path
            
        Returns:
            Dictionary mapping relative paths to file information
        """
        self.folder_map = {}
        
        if input_path.is_file():
            # Single file mode
            self.folder_map['.'] = {
                'full_path': input_path.parent,
                'files': [input_path.name],
                'pptx_files': [input_path.name] if input_path.suffix.lower() == '.pptx' else [],
                'txt_files': [input_path.name] if input_path.suffix.lower() == '.txt' else [],
                'all_files': {input_path.name: input_path}
            }
        else:
            # Recursive directory scan
            for root, dirs, files in os.walk(input_path):
                # Calculate relative path from input directory
                rel_path = os.path.relpath(root, input_path)
                
                # Filter and categorize files
                pptx_files = []
                txt_files = []
                all_files = {}
                
                for file in files:
                    file_path = Path(root) / file
                    ext = file_path.suffix.lower()
                    
                    # Store file path
                    all_files[file] = file_path
                    
                    # Categorize by type
                    if ext == '.pptx':
                        pptx_files.append(file)
                    elif ext == '.txt':
                        txt_files.append(file)
                
                # Store folder information
                if files:  # Only store folders that contain files
                    self.folder_map[rel_path] = {
                        'full_path': Path(root),
                        'files': files,
                        'pptx_files': pptx_files,
                        'txt_files': txt_files,
                        'all_files': all_files
                    }
        
        logger.info(f"Scanned {len(self.folder_map)} folders with files")
        return self.folder_map
    
    def create_output_structure(self, input_path: Path, output_path: Path, 
                               target_lang: str = None) -> Path:
        """
        Create output directory structure mirroring the input.
        
        Args:
            input_path: Root input directory path
            output_path: Root output directory path
            target_lang: Optional target language for subdirectory
            
        Returns:
            Root output path for this language
        """
        # Create language-specific output directory if specified
        if target_lang:
            lang_output_path = output_path / target_lang
        else:
            lang_output_path = output_path
        
        # Create root output directory
        lang_output_path.mkdir(parents=True, exist_ok=True)
        
        # If input is a file, no subdirectories needed
        if input_path.is_file():
            return lang_output_path
        
        # Create all subdirectories that exist in input
        for rel_path in self.folder_map.keys():
            if rel_path != '.':
                output_dir = lang_output_path / rel_path
                output_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created output directory: {output_dir}")
        
        return lang_output_path
    
    def get_output_path_for_file(self, input_file: Path, input_root: Path, 
                                 output_root: Path, suffix: str = None) -> Path:
        """
        Get the output path for a file, preserving folder structure.
        
        Args:
            input_file: Path to the input file
            input_root: Root input directory
            output_root: Root output directory
            suffix: Optional suffix to add to filename
            
        Returns:
            Corresponding output file path
        """
        # Calculate relative path from input root
        rel_path = input_file.relative_to(input_root)
        
        # Construct output path
        if suffix:
            # Add suffix before extension
            stem = rel_path.stem
            ext = rel_path.suffix
            new_name = f"{stem}{suffix}{ext}"
            output_file = output_root / rel_path.parent / new_name
        else:
            output_file = output_root / rel_path
        
        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        return output_file
    
    def get_files_by_type(self, file_type: str) -> List[Tuple[str, Path]]:
        """
        Get all files of a specific type from the folder map.
        
        Args:
            file_type: Type of files to get ('pptx', 'txt', etc.)
            
        Returns:
            List of tuples (relative_folder_path, file_path)
        """
        files = []
        
        for rel_path, folder_info in self.folder_map.items():
            if file_type == 'pptx':
                for pptx_file in folder_info['pptx_files']:
                    files.append((rel_path, folder_info['all_files'][pptx_file]))
            elif file_type == 'txt':
                for txt_file in folder_info['txt_files']:
                    files.append((rel_path, folder_info['all_files'][txt_file]))
            else:
                # Generic file type handling
                for file_name, file_path in folder_info['all_files'].items():
                    if self._matches_type(file_path, file_type):
                        files.append((rel_path, file_path))
        
        return files
    
    def _matches_type(self, file_path: Path, file_type: str) -> bool:
        """
        Check if a file matches a specific type.
        
        Args:
            file_path: Path to check
            file_type: Type to match against
            
        Returns:
            True if file matches the type
        """
        ext = file_path.suffix.lower()
        
        if file_type in self.supported_extensions:
            return ext in self.supported_extensions[file_type]
        
        return False
    
    def get_folder_stats(self) -> Dict[str, int]:
        """
        Get statistics about the scanned folder structure.
        
        Returns:
            Dictionary with file counts by type
        """
        stats = {
            'total_folders': len(self.folder_map),
            'total_files': 0,
            'pptx_files': 0,
            'txt_files': 0
        }
        
        for folder_info in self.folder_map.values():
            stats['total_files'] += len(folder_info['files'])
            stats['pptx_files'] += len(folder_info['pptx_files'])
            stats['txt_files'] += len(folder_info['txt_files'])
        
        return stats