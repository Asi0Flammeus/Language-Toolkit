import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple

import boto3

logger = logging.getLogger(__name__)


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
    def download_files(self, keys: List[str], dest_dir: Path) -> List[Path]:
        """Download a list of *keys* in *self.bucket* to *dest_dir*.

        Returns a list of local file paths.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        local_paths: List[Path] = []
        for key in keys:
            filename = Path(key).name
            local_path = dest_dir / filename
            logger.info("[S3] Downloading %s -> %s", key, local_path)
            self._client.download_file(self.bucket, key, str(local_path))
            local_paths.append(local_path)
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