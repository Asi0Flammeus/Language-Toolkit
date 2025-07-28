import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# File size limits (same as api_server.py)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", str(100 * 1024 * 1024)))  # 100MB default
MAX_PPTX_SIZE = int(os.getenv("MAX_PPTX_SIZE", str(50 * 1024 * 1024)))   # 50MB for PPTX
MAX_AUDIO_SIZE = int(os.getenv("MAX_AUDIO_SIZE", str(200 * 1024 * 1024))) # 200MB for audio
MAX_TEXT_SIZE = int(os.getenv("MAX_TEXT_SIZE", str(10 * 1024 * 1024)))    # 10MB for text


class S3ClientWrapper:
    """Light-weight helper around *boto3* for common operations used by the API.

    The class fetches credentials from the standard *boto3* resolution chain
    (env vars, config file, IAM role, …).  A default bucket name can be provided
    via the ``S3_BUCKET`` environment variable but individual calls may also
    specify another bucket explicitly.
    """

    def __init__(self, bucket: Optional[str] = None):
        self.bucket = bucket or os.getenv("S3_BUCKET")
        if not self.bucket:
            raise RuntimeError("S3 bucket name not provided (env S3_BUCKET not set)")
        
        # Get custom S3 configuration from environment
        s3_endpoint = os.getenv("S3_ENDPOINT")
        s3_access_key = os.getenv("S3_ACCESS_KEY")
        s3_secret_key = os.getenv("S3_SECRET_KEY")
        s3_region = os.getenv("S3_REGION")
        
        if not s3_access_key or not s3_secret_key:
            raise RuntimeError("S3 credentials not found. Please set S3_ACCESS_KEY and S3_SECRET_KEY environment variables.")
        
        # Configure boto3 client with custom endpoint and credentials
        client_config = {
            'aws_access_key_id': s3_access_key,
            'aws_secret_access_key': s3_secret_key,
        }
        
        if s3_region:
            client_config['region_name'] = s3_region
            
        if s3_endpoint:
            client_config['endpoint_url'] = s3_endpoint
            
        self._client = boto3.client("s3", **client_config)

    # ---------------------------------------------------------------------
    # Download helpers
    # ---------------------------------------------------------------------
    def _get_file_type_from_key(self, key: str) -> str:
        """Determine file type category from S3 key for size validation."""
        extension = Path(key).suffix.lower()
        
        if extension == '.pptx':
            return "pptx"
        elif extension in ['.txt']:
            return "text"
        elif extension in ['.wav', '.mp3', '.m4a', '.webm', '.mp4', '.mpga', '.mpeg', '.ogg', '.flac']:
            return "audio"
        else:
            return "general"
    
    def _validate_s3_file_size(self, key: str) -> None:
        """Check S3 object size before downloading."""
        try:
            response = self._client.head_object(Bucket=self.bucket, Key=key)
            file_size = response['ContentLength']
            
            # Determine size limit based on file type
            file_type = self._get_file_type_from_key(key)
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
                raise ValueError(
                    f"S3 file '{key}' is too large ({actual_mb:.1f}MB). "
                    f"Maximum allowed size for {file_type} files is {size_mb:.1f}MB."
                )
            
            logger.info(f"S3 file size validation passed: {key} ({file_size} bytes)")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise FileNotFoundError(f"S3 object not found: {key}")
            elif error_code == 'Forbidden':
                raise PermissionError(f"Access denied to S3 object: {key}")
            else:
                raise RuntimeError(f"Failed to check S3 object size: {e}")

    def download_files(self, keys: List[str], dest_dir: Path, validate_size: bool = True) -> List[Path]:
        """Download a list of *keys* in *self.bucket* to *dest_dir*.

        Args:
            keys: List of S3 object keys to download
            dest_dir: Local directory to save files
            validate_size: Whether to validate file sizes before download

        Returns:
            List of local file paths.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        local_paths: List[Path] = []
        
        for key in keys:
            # Validate file size if requested
            if validate_size:
                self._validate_s3_file_size(key)
            
            filename = Path(key).name
            local_path = dest_dir / filename
            logger.info("[S3] Downloading %s -> %s", key, local_path)
            
            try:
                self._client.download_file(self.bucket, key, str(local_path))
                local_paths.append(local_path)
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NoSuchKey':
                    raise FileNotFoundError(f"S3 object not found: {key}")
                elif error_code == 'Forbidden':
                    raise PermissionError(f"Access denied to S3 object: {key}")
                else:
                    raise RuntimeError(f"Failed to download S3 object: {e}")
                    
        return local_paths

    # ------------------------------------------------------------------
    # Upload helpers
    # ------------------------------------------------------------------
    def upload_files(self, files: List[Path], dest_prefix: Optional[str] = None) -> List[str]:
        """Upload *files* to ``dest_prefix`` inside *self.bucket*.

        Returns the list of S3 keys created.
        """
        dest_prefix = (dest_prefix or "").lstrip("/")
        s3_keys: List[str] = []
        for file_path in files:
            key = f"{dest_prefix}{file_path.name}" if dest_prefix else file_path.name
            logger.info("[S3] Uploading %s -> s3://%s/%s", file_path, self.bucket, key)
            self._client.upload_file(str(file_path), self.bucket, key)
            s3_keys.append(key)
        return s3_keys

    def upload_files_with_mapping(self, files: List[Path], input_keys: List[str], 
                                  output_prefix: Optional[str] = None) -> List[str]:
        """Upload files using a mapping based on original input keys.
        
        This preserves the exact directory structure from input_keys and only
        replaces the filename with the processed result filename.
        
        Args:
            files: Local file paths to upload
            input_keys: Original S3 keys that were downloaded
            output_prefix: Optional prefix to replace the original path prefix 
                          (if None, keeps original structure with "translated_" filename prefix)
            
        Returns:
            List of S3 keys created
        """
        if len(files) != len(input_keys):
            raise ValueError(f"Number of files ({len(files)}) must match number of input keys ({len(input_keys)})")
        
        s3_keys: List[str] = []
        
        for file_path, original_key in zip(files, input_keys):
            original_path = Path(original_key)
            
            if output_prefix:
                # Replace the root directory with output_prefix but keep the subdirectory structure
                # Example: contribute/abc/en/pptx/file.pptx -> translated/abc/en/pptx/translated_file.pptx
                original_parts = original_path.parts
                if len(original_parts) > 1:
                    # Keep everything after the first directory part
                    subdirs = "/".join(original_parts[1:-1])  # Skip first dir and filename
                    if subdirs:
                        key = f"{output_prefix.rstrip('/')}/{subdirs}/{file_path.name}"
                    else:
                        key = f"{output_prefix.rstrip('/')}/{file_path.name}"
                else:
                    key = f"{output_prefix.rstrip('/')}/{file_path.name}"
            else:
                # Keep EXACT original directory structure with "translated_" filename prefix
                # Example: contribute/abc/en/pptx/file.pptx -> contribute/abc/en/pptx/translated_file.pptx
                original_dir = str(original_path.parent) if original_path.parent != Path('.') else ""
                
                # Ensure filename has "translated_" prefix if not already present
                filename = file_path.name
                if not filename.startswith("translated_"):
                    filename = f"translated_{filename}"
                
                key = f"{original_dir}/{filename}" if original_dir else filename
            
            logger.info("[S3] Uploading %s -> s3://%s/%s", file_path, self.bucket, key)
            self._client.upload_file(str(file_path), self.bucket, key)
            s3_keys.append(key)
            
        return s3_keys 

    # ------------------------------------------------------------------
    # Listing helpers
    # ------------------------------------------------------------------
    def list_files(self, prefix: str, extensions: Optional[List[str]] = None) -> List[str]:
        """List all object keys under *prefix* (non-recursive) optionally filtered by *extensions*.

        Args:
            prefix: S3 key prefix to search (must end with '/')
            extensions: list like ['.pptx', '.txt']; comparison is case-insensitive.

        Returns:
            List of S3 keys.
        """
        paginator = self._client.get_paginator("list_objects_v2")
        keys: List[str] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if extensions:
                    if not any(key.lower().endswith(ext.lower()) for ext in extensions):
                        continue
                keys.append(key)
        return keys 