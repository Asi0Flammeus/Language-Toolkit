"""
File operation utilities for Language Toolkit.
Provides common file handling functions used across GUI and API applications.
"""

import json
import logging
import os
import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)

# Common media types mapping
MEDIA_TYPES = {
    '.pdf': 'application/pdf',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.txt': 'text/plain',
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.m4a': 'audio/mp4',
    '.aac': 'audio/aac',
    '.ogg': 'audio/ogg',
    '.flac': 'audio/flac',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff',
    '.webp': 'image/webp',
    '.mp4': 'video/mp4',
    '.avi': 'video/x-msvideo',
    '.mov': 'video/quicktime',
    '.mkv': 'video/x-matroska',
    '.webm': 'video/webm',
    '.json': 'application/json',
    '.zip': 'application/zip',
}

# Invalid filename characters (Windows + Unix)
INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\x00-\x1f]'

class FileUtilsError(Exception):
    """Base exception for file utility errors"""
    pass

def create_temp_dir(prefix: str = "language_toolkit_", parent_dir: Optional[Path] = None) -> Path:
    """
    Create a temporary directory with optional parent directory.
    
    Args:
        prefix: Prefix for the temporary directory name
        parent_dir: Parent directory for the temp dir (uses system default if None)
        
    Returns:
        Path to the created temporary directory
        
    Raises:
        FileUtilsError: If directory creation fails
    """
    try:
        if parent_dir:
            parent_dir = Path(parent_dir)
            parent_dir.mkdir(parents=True, exist_ok=True)
            temp_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=str(parent_dir)))
        else:
            temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
        
        logger.debug(f"Created temporary directory: {temp_dir}")
        return temp_dir
    except Exception as e:
        raise FileUtilsError(f"Failed to create temporary directory: {e}")

def safe_cleanup(path: Union[str, Path], ignore_errors: bool = True) -> bool:
    """
    Safely remove a file or directory.
    
    Args:
        path: Path to file or directory to remove
        ignore_errors: Whether to ignore errors during cleanup
        
    Returns:
        True if cleanup was successful, False otherwise
    """
    path = Path(path)
    
    try:
        if not path.exists():
            return True
            
        if path.is_file():
            path.unlink()
            logger.debug(f"Removed file: {path}")
        elif path.is_dir():
            shutil.rmtree(path)
            logger.debug(f"Removed directory: {path}")
        else:
            logger.warning(f"Unknown path type for cleanup: {path}")
            
        return True
        
    except Exception as e:
        error_msg = f"Failed to cleanup {path}: {e}"
        if ignore_errors:
            logger.warning(error_msg)
            return False
        else:
            raise FileUtilsError(error_msg)

def ensure_directory_exists(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path to ensure exists
        
    Returns:
        Path object for the directory
        
    Raises:
        FileUtilsError: If directory creation fails
    """
    path = Path(path)
    
    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {path}")
        return path
    except Exception as e:
        raise FileUtilsError(f"Failed to create directory {path}: {e}")

def validate_file_path(
    path: Union[str, Path], 
    must_exist: bool = True, 
    allowed_extensions: Optional[Set[str]] = None
) -> Path:
    """
    Validate a file path with optional existence and extension checks.
    
    Args:
        path: File path to validate
        must_exist: Whether the file must exist
        allowed_extensions: Set of allowed extensions (e.g., {'.txt', '.pdf'})
        
    Returns:
        Validated Path object
        
    Raises:
        FileUtilsError: If validation fails
    """
    path = Path(path)
    
    if must_exist and not path.exists():
        raise FileUtilsError(f"File does not exist: {path}")
        
    if must_exist and not path.is_file():
        raise FileUtilsError(f"Path is not a file: {path}")
        
    if allowed_extensions:
        ext = path.suffix.lower()
        if ext not in allowed_extensions:
            raise FileUtilsError(
                f"Invalid file extension '{ext}'. Allowed: {', '.join(sorted(allowed_extensions))}"
            )
    
    return path

def get_file_extension(path: Union[str, Path], lowercase: bool = True) -> str:
    """
    Get file extension, optionally converting to lowercase.
    
    Args:
        path: File path
        lowercase: Whether to convert extension to lowercase
        
    Returns:
        File extension including the dot (e.g., '.txt')
    """
    ext = Path(path).suffix
    return ext.lower() if lowercase else ext

def create_output_filename(
    input_path: Union[str, Path],
    prefix: str = "",
    suffix: str = "",
    new_extension: Optional[str] = None
) -> str:
    """
    Create an output filename based on input file.
    
    Args:
        input_path: Input file path
        prefix: Prefix to add to filename
        suffix: Suffix to add to stem (before extension)
        new_extension: New extension to use (e.g., '.pdf')
        
    Returns:
        Generated output filename
        
    Examples:
        create_output_filename("doc.txt", prefix="translated_") -> "translated_doc.txt"
        create_output_filename("doc.txt", suffix="_fr") -> "doc_fr.txt"
        create_output_filename("doc.txt", new_extension=".pdf") -> "doc.pdf"
    """
    input_path = Path(input_path)
    
    # Build the filename components
    stem = input_path.stem
    extension = new_extension if new_extension else input_path.suffix
    
    # Add suffix to stem if provided
    if suffix:
        stem = f"{stem}{suffix}"
        
    # Build final filename
    filename = f"{stem}{extension}"
    
    # Add prefix if provided
    if prefix:
        filename = f"{prefix}{filename}"
        
    return filename

def should_skip_processing(
    input_path: Union[str, Path],
    output_path: Union[str, Path],
    check_exists: bool = True
) -> bool:
    """
    Check if processing should be skipped based on existing output.
    
    Args:
        input_path: Input file path (for logging)
        output_path: Output file path to check
        check_exists: Whether to perform the existence check
        
    Returns:
        True if processing should be skipped, False otherwise
    """
    if not check_exists:
        return False
        
    output_path = Path(output_path)
    if output_path.exists():
        logger.info(f"Skipping {Path(input_path).name} - output already exists: {output_path.name}")
        return True
        
    return False

def load_json_file(
    path: Union[str, Path],
    default: Any = None,
    create_if_missing: bool = False
) -> Any:
    """
    Load JSON data from a file with error handling.
    
    Args:
        path: Path to JSON file
        default: Default value to return if file doesn't exist or is invalid
        create_if_missing: Create file with default value if it doesn't exist
        
    Returns:
        Loaded JSON data or default value
        
    Raises:
        FileUtilsError: If file loading fails and no default is provided
    """
    path = Path(path)
    
    try:
        if not path.exists():
            if create_if_missing and default is not None:
                save_json_file(path, default)
                return default
            elif default is not None:
                logger.warning(f"JSON file not found: {path}. Using default value.")
                return default
            else:
                raise FileUtilsError(f"JSON file not found: {path}")
                
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logger.debug(f"Loaded JSON file: {path}")
            return data
            
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in {path}: {e}"
        if default is not None:
            logger.error(f"{error_msg}. Using default value.")
            return default
        else:
            raise FileUtilsError(error_msg)
    except Exception as e:
        error_msg = f"Failed to load JSON file {path}: {e}"
        if default is not None:
            logger.error(f"{error_msg}. Using default value.")
            return default
        else:
            raise FileUtilsError(error_msg)

def save_json_file(
    path: Union[str, Path],
    data: Any,
    indent: int = 4,
    ensure_ascii: bool = False
) -> bool:
    """
    Save data to a JSON file with error handling.
    
    Args:
        path: Path to save JSON file
        data: Data to save
        indent: JSON indentation level
        ensure_ascii: Force ASCII encoding
        
    Returns:
        True if save was successful, False otherwise
        
    Raises:
        FileUtilsError: If save fails
    """
    path = Path(path)
    
    try:
        # Ensure parent directory exists
        ensure_directory_exists(path.parent)
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
            
        logger.debug(f"Saved JSON file: {path}")
        return True
        
    except Exception as e:
        raise FileUtilsError(f"Failed to save JSON file {path}: {e}")

def collect_files(
    directory: Union[str, Path],
    extensions: Optional[Set[str]] = None,
    recursive: bool = True,
    exclude_hidden: bool = True
) -> List[Path]:
    """
    Collect files from a directory with optional filtering.
    
    Args:
        directory: Directory to search
        extensions: Set of allowed extensions (e.g., {'.txt', '.pdf'})
        recursive: Whether to search recursively
        exclude_hidden: Whether to exclude hidden files (starting with '.')
        
    Returns:
        List of Path objects for matching files
        
    Raises:
        FileUtilsError: If directory doesn't exist or can't be accessed
    """
    directory = Path(directory)
    
    if not directory.exists():
        raise FileUtilsError(f"Directory does not exist: {directory}")
        
    if not directory.is_dir():
        raise FileUtilsError(f"Path is not a directory: {directory}")
    
    try:
        files = []
        pattern = "**/*" if recursive else "*"
        
        for item in directory.glob(pattern):
            if not item.is_file():
                continue
                
            # Exclude hidden files if requested
            if exclude_hidden and item.name.startswith('.'):
                continue
                
            # Filter by extensions if provided
            if extensions is not None:
                if item.suffix.lower() not in extensions:
                    continue
                    
            files.append(item)
            
        # Sort files for consistent ordering
        files.sort(key=lambda x: str(x).lower())
        
        logger.debug(f"Collected {len(files)} files from {directory}")
        return files
        
    except Exception as e:
        raise FileUtilsError(f"Failed to collect files from {directory}: {e}")

def get_media_type(file_path: Union[str, Path]) -> str:
    """
    Get media type for a file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        MIME type string (defaults to 'application/octet-stream')
    """
    extension = get_file_extension(file_path, lowercase=True)
    return MEDIA_TYPES.get(extension, 'application/octet-stream')

def safe_write_file(
    path: Union[str, Path],
    content: Union[str, bytes],
    mode: str = "wb",
    encoding: Optional[str] = "utf-8"
) -> bool:
    """
    Safely write content to a file with error handling.
    
    Args:
        path: File path to write to
        content: Content to write
        mode: File open mode ('w', 'wb', 'a', etc.)
        encoding: Text encoding (used for text modes)
        
    Returns:
        True if write was successful
        
    Raises:
        FileUtilsError: If write fails
    """
    path = Path(path)
    
    try:
        # Ensure parent directory exists
        ensure_directory_exists(path.parent)
        
        # Determine if we're in text or binary mode
        is_text_mode = 'b' not in mode
        
        if is_text_mode and isinstance(content, bytes):
            content = content.decode(encoding or 'utf-8')
        elif not is_text_mode and isinstance(content, str):
            content = content.encode(encoding or 'utf-8')
        
        # Write the file
        if is_text_mode:
            with open(path, mode, encoding=encoding) as f:
                f.write(content)
        else:
            with open(path, mode) as f:
                f.write(content)
                
        logger.debug(f"Wrote file: {path} ({len(content)} {'chars' if is_text_mode else 'bytes'})")
        return True
        
    except Exception as e:
        raise FileUtilsError(f"Failed to write file {path}: {e}")

@contextmanager
def temp_working_directory(prefix: str = "language_toolkit_"):
    """
    Context manager for temporary working directory.
    
    Args:
        prefix: Prefix for temporary directory name
        
    Yields:
        Path to temporary directory
        
    Example:
        with temp_working_directory() as temp_dir:
            # Work with files in temp_dir
            output_file = temp_dir / "output.txt"
            # temp_dir is automatically cleaned up when exiting the context
    """
    temp_dir = None
    try:
        temp_dir = create_temp_dir(prefix)
        yield temp_dir
    finally:
        if temp_dir:
            safe_cleanup(temp_dir)

def copy_preserving_structure(
    source_files: List[Path],
    source_root: Path,
    target_root: Path
) -> List[Path]:
    """
    Copy files preserving directory structure.
    
    Args:
        source_files: List of source file paths
        source_root: Root directory of source files
        target_root: Root directory for target files
        
    Returns:
        List of copied file paths
        
    Raises:
        FileUtilsError: If copying fails
    """
    source_root = Path(source_root)
    target_root = Path(target_root)
    copied_files = []
    
    try:
        for source_file in source_files:
            source_file = Path(source_file)
            
            # Calculate relative path from source root
            rel_path = source_file.relative_to(source_root)
            target_file = target_root / rel_path
            
            # Ensure target directory exists
            ensure_directory_exists(target_file.parent)
            
            # Copy the file
            shutil.copy2(source_file, target_file)
            copied_files.append(target_file)
            
        logger.debug(f"Copied {len(copied_files)} files preserving structure")
        return copied_files
        
    except Exception as e:
        raise FileUtilsError(f"Failed to copy files preserving structure: {e}")

def get_relative_path(path: Union[str, Path], base: Union[str, Path]) -> Path:
    """
    Get relative path with error handling.
    
    Args:
        path: Path to make relative
        base: Base path to calculate relative to
        
    Returns:
        Relative path
        
    Raises:
        FileUtilsError: If relative path calculation fails
    """
    try:
        return Path(path).relative_to(Path(base))
    except ValueError as e:
        raise FileUtilsError(f"Cannot calculate relative path from {base} to {path}: {e}")

def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize filename by replacing invalid characters.
    
    Args:
        filename: Original filename
        replacement: Character to replace invalid characters with
        
    Returns:
        Sanitized filename
    """
    # Replace invalid characters
    sanitized = re.sub(INVALID_FILENAME_CHARS, replacement, filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Ensure filename is not empty
    if not sanitized:
        sanitized = "file"
        
    # Limit length (most filesystems support 255 characters)
    if len(sanitized) > 250:  # Leave room for extensions
        sanitized = sanitized[:250]
        
    return sanitized

def get_file_size(path: Union[str, Path]) -> int:
    """
    Get file size in bytes.
    
    Args:
        path: File path
        
    Returns:
        File size in bytes
        
    Raises:
        FileUtilsError: If file doesn't exist or can't be accessed
    """
    path = Path(path)
    
    try:
        return path.stat().st_size
    except Exception as e:
        raise FileUtilsError(f"Failed to get size of {path}: {e}")

def get_file_size_mb(path: Union[str, Path]) -> float:
    """
    Get file size in megabytes.
    
    Args:
        path: File path
        
    Returns:
        File size in MB (rounded to 2 decimal places)
    """
    size_bytes = get_file_size(path)
    return round(size_bytes / (1024 * 1024), 2)

def is_empty_file(path: Union[str, Path]) -> bool:
    """
    Check if a file is empty.
    
    Args:
        path: File path
        
    Returns:
        True if file is empty, False otherwise
    """
    try:
        return get_file_size(path) == 0
    except FileUtilsError:
        return True  # Assume non-existent files are "empty"