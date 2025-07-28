"""
Shared validation utilities for Language Toolkit.
Provides consistent validation functions used across GUI and API applications.
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional, Set, Tuple, List, Union, Any

try:
    from fastapi import HTTPException, UploadFile
except ImportError:
    # Allow module to be imported in non-API contexts
    HTTPException = None
    UploadFile = None

logger = logging.getLogger(__name__)

# Configuration constants
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(100 * 1024 * 1024)))  # 100MB default
MAX_PPTX_SIZE = int(os.getenv("MAX_PPTX_SIZE", str(50 * 1024 * 1024)))   # 50MB for PPTX
MAX_AUDIO_SIZE = int(os.getenv("MAX_AUDIO_SIZE", str(200 * 1024 * 1024))) # 200MB for audio
MAX_TEXT_SIZE = int(os.getenv("MAX_TEXT_SIZE", str(10 * 1024 * 1024)))    # 10MB for text

# Supported file extensions
SUPPORTED_PPTX_EXTENSIONS = {".pptx", ".ppt", ".potx", ".pps", ".ppsx"}
SUPPORTED_TEXT_EXTENSIONS = {".txt"}
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".mp4", ".mpga", ".mpeg", ".ogg", ".flac"}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"}
SUPPORTED_CONVERSION_FORMATS = {"pdf", "png", "webp"}

class ValidationError(Exception):
    """Base exception for validation errors"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

def load_supported_languages() -> Tuple[Set[str], Set[str]]:
    """
    Load supported languages from supported_languages.json
    
    Returns:
        Tuple of (source_languages, target_languages) sets
    """
    try:
        config_path = Path(__file__).parent.parent / "supported_languages.json"
        with open(config_path, "r") as f:
            languages = json.load(f)
        source_langs = set(languages.get("source_languages", {}).keys())
        target_langs = set(languages.get("target_languages", {}).keys())
        return source_langs, target_langs
    except Exception as e:
        logger.error(f"Failed to load supported_languages.json: {e}")
        # Fallback to default languages if file not found
        source_langs = {
            "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "hu", "id", 
            "it", "ja", "lt", "lv", "nl", "pl", "pt", "ro", "ru", "sk", "sl", "sv", 
            "tr", "uk", "zh"
        }
        target_langs = {
            "bg", "cs", "da", "de", "el", "en-gb", "en-us", "es", "et", "fi", "fr", 
            "hu", "id", "it", "ja", "ko", "lt", "lv", "nl", "pl", "pt-br", "pt-pt", 
            "ro", "ru", "sk", "sl", "sv", "tr", "uk", "zh"
        }
        return source_langs, target_langs

# Load language constants
VALID_SOURCE_LANGUAGES, VALID_TARGET_LANGUAGES = load_supported_languages()

def get_file_type_from_filename(filename: str) -> str:
    """
    Determine file type category from filename for size validation.
    
    Args:
        filename: Name of the file
        
    Returns:
        File type category: 'pptx', 'text', 'audio', or 'general'
    """
    if not filename:
        return "general"
    
    extension = Path(filename).suffix.lower()
    
    if extension in SUPPORTED_PPTX_EXTENSIONS:
        return "pptx"
    elif extension in SUPPORTED_TEXT_EXTENSIONS:
        return "text"
    elif extension in SUPPORTED_AUDIO_EXTENSIONS:
        return "audio"
    else:
        return "general"

def validate_file_size(file_size: int, filename: str = "", file_type: str = "general") -> None:
    """
    Validate file size against configured limits.
    
    Args:
        file_size: Size of the file in bytes
        filename: Name of the file (for error messages)
        file_type: Type of file for specific size limits ('pptx', 'audio', 'text', 'general')
        
    Raises:
        ValidationError: If file size exceeds the limit
    """
    # Determine size limit based on file type
    size_limits = {
        "pptx": MAX_PPTX_SIZE,
        "audio": MAX_AUDIO_SIZE,
        "text": MAX_TEXT_SIZE,
        "general": MAX_FILE_SIZE
    }
    
    max_size = size_limits.get(file_type, MAX_FILE_SIZE)
    
    if file_size > max_size:
        size_mb = max_size / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        error_msg = (
            f"File '{filename}' is too large ({actual_mb:.1f}MB). "
            f"Maximum allowed size for {file_type} files is {size_mb:.1f}MB."
        )
        raise ValidationError(error_msg, 413)
    
    logger.debug(f"File size validation passed: {filename} ({file_size} bytes)")

def validate_fastapi_file_size(file: 'UploadFile', file_type: str = "general") -> None:
    """
    Validate uploaded file size against configured limits (FastAPI version).
    
    Args:
        file: The uploaded file to validate
        file_type: Type of file for specific size limits ('pptx', 'audio', 'text', 'general')
        
    Raises:
        HTTPException: If file size exceeds the limit
    """
    if HTTPException is None:
        raise ImportError("FastAPI not available. Use validate_file_size() instead.")
        
    if not hasattr(file, 'size') or file.size is None:
        # Try to get size from file content if size attribute not available
        if hasattr(file.file, 'seek') and hasattr(file.file, 'tell'):
            current_pos = file.file.tell()
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(current_pos)  # Return to original position
        else:
            # If we can't determine size, allow it to proceed (will be caught later if too large)
            logger.warning(f"Could not determine size for file: {file.filename}")
            return
    else:
        file_size = file.size
    
    try:
        validate_file_size(file_size, file.filename or "unknown", file_type)
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

def validate_language_code(language: str, is_target: bool = False) -> str:
    """
    Validate language code against supported languages.
    
    Args:
        language: Language code to validate
        is_target: Whether this is a target language (allows more variants)
        
    Returns:
        Normalized language code (lowercase, stripped)
        
    Raises:
        ValidationError: If language code is invalid
    """
    if not language or not isinstance(language, str):
        raise ValidationError("Language code must be a non-empty string")
    
    language = language.lower().strip()
    valid_languages = VALID_TARGET_LANGUAGES if is_target else VALID_SOURCE_LANGUAGES
    
    if language not in valid_languages:
        lang_type = "target" if is_target else "source"
        error_msg = (
            f"Invalid {lang_type} language code: '{language}'. "
            f"Supported codes: {', '.join(sorted(valid_languages))}"
        )
        raise ValidationError(error_msg)
    
    return language

def validate_file_extension(filename: str, allowed_extensions: Set[str]) -> str:
    """
    Validate file extension against allowed extensions.
    
    Args:
        filename: Name of the file to validate
        allowed_extensions: Set of allowed extensions (with dots, e.g. {'.txt', '.pdf'})
        
    Returns:
        Normalized filename
        
    Raises:
        ValidationError: If file extension is not allowed
    """
    if not filename:
        raise ValidationError("Filename cannot be empty")
    
    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions:
        error_msg = (
            f"Unsupported file format: '{extension}'. "
            f"Supported formats: {', '.join(sorted(allowed_extensions))}"
        )
        raise ValidationError(error_msg)
    
    return filename

def validate_output_format(format_str: str, allowed_formats: Set[str]) -> str:
    """
    Validate output format against allowed formats.
    
    Args:
        format_str: Format string to validate
        allowed_formats: Set of allowed format strings
        
    Returns:
        Normalized format string (lowercase, stripped)
        
    Raises:
        ValidationError: If format is not allowed
    """
    if not format_str or not isinstance(format_str, str):
        raise ValidationError("Output format must be a non-empty string")
    
    format_str = format_str.lower().strip()
    if format_str not in allowed_formats:
        error_msg = (
            f"Invalid output format: '{format_str}'. "
            f"Supported formats: {', '.join(sorted(allowed_formats))}"
        )
        raise ValidationError(error_msg)
    
    return format_str

def validate_s3_path(path: str) -> bool:
    """
    Validate S3 path to prevent directory traversal attacks.
    
    Args:
        path: S3 path to validate
        
    Returns:
        True if path is valid, False otherwise
    """
    # Check for path traversal attempts
    if ".." in path or path.startswith("/") or "\\" in path:
        return False
    
    # Check for suspicious patterns
    suspicious_patterns = ["~", "${", "$(", "`", "%", "&", "|", ";", "<", ">", "\n", "\r", "\0"]
    for pattern in suspicious_patterns:
        if pattern in path:
            return False
    
    # Ensure path components are reasonable
    parts = path.split("/")
    for part in parts:
        if len(part) > 255 or len(part) == 0:
            return False
    
    return True

def validate_duration_per_slide(duration: Optional[float]) -> float:
    """
    Validate duration per slide parameter.
    
    Args:
        duration: Duration value to validate
        
    Returns:
        Validated duration value
        
    Raises:
        ValidationError: If duration is invalid
    """
    if duration is None:
        return 3.0  # Default value
    
    if not isinstance(duration, (int, float)):
        raise ValidationError("Duration must be a number")
    
    if duration <= 0:
        raise ValidationError("Duration must be greater than 0")
    
    if duration > 60:
        raise ValidationError("Duration must be 60 seconds or less")
    
    return float(duration)

def validate_non_empty_string(value: str, field_name: str) -> str:
    """
    Validate that a string field is non-empty.
    
    Args:
        value: String value to validate
        field_name: Name of the field for error messages
        
    Returns:
        Stripped string value
        
    Raises:
        ValidationError: If string is empty or invalid
    """
    if not value or not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string")
    
    return value.strip()

def validate_string_list(value: List[str], field_name: str, min_length: int = 1) -> List[str]:
    """
    Validate that a list contains valid non-empty strings.
    
    Args:
        value: List of strings to validate
        field_name: Name of the field for error messages
        min_length: Minimum number of items required
        
    Returns:
        List of validated strings
        
    Raises:
        ValidationError: If list is invalid
    """
    if not value or len(value) < min_length:
        raise ValidationError(f"{field_name} must contain at least {min_length} item(s)")
    
    validated_items = []
    for i, item in enumerate(value):
        if not item or not isinstance(item, str) or not item.strip():
            raise ValidationError(f"{field_name}[{i}] must be a non-empty string")
        validated_items.append(item.strip())
    
    return validated_items

# FastAPI-specific wrapper functions
def raise_http_exception_from_validation_error(func):
    """
    Decorator to convert ValidationError to HTTPException for FastAPI endpoints.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            if HTTPException is not None:
                raise HTTPException(status_code=e.status_code, detail=e.message)
            else:
                raise e
    return wrapper

# Convenience functions for FastAPI
if HTTPException is not None:
    @raise_http_exception_from_validation_error
    def validate_language_code_http(language: str, is_target: bool = False) -> str:
        """FastAPI version of validate_language_code that raises HTTPException"""
        return validate_language_code(language, is_target)
    
    @raise_http_exception_from_validation_error
    def validate_file_extension_http(filename: str, allowed_extensions: Set[str]) -> str:
        """FastAPI version of validate_file_extension that raises HTTPException"""
        return validate_file_extension(filename, allowed_extensions)
    
    @raise_http_exception_from_validation_error
    def validate_output_format_http(format_str: str, allowed_formats: Set[str]) -> str:
        """FastAPI version of validate_output_format that raises HTTPException"""
        return validate_output_format(format_str, allowed_formats)
    
    @raise_http_exception_from_validation_error
    def validate_duration_per_slide_http(duration: Optional[float]) -> float:
        """FastAPI version of validate_duration_per_slide that raises HTTPException"""
        return validate_duration_per_slide(duration)