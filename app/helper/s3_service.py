"""
S3 Service for uploading, deleting, and managing image files in Amazon S3.

This module provides a high-level abstraction for S3 operations:
- Upload files with automatic key generation
- Delete files from S3
- Generate public URLs from image keys
- Validate image keys and formats
- Handle S3 errors gracefully

The service uses boto3 to interact with AWS S3 and follows FastAPI best practices
with proper type hints, logging, and exception handling.

Example:
    from app.helper.s3_service import S3Service
    
    s3_service = S3Service()
    image_key = s3_service.upload_file(
        file_content=file_bytes,
        original_filename="photo.jpg",
        folder="users/profiles"
    )
    url = s3_service.generate_image_url(image_key)
"""

import logging
import mimetypes
import uuid
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from .config import get_s3_config
from .image_utils import validate_image_key

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


class S3ServiceError(Exception):
    """Base exception for S3Service operations."""

    pass


class S3UploadError(S3ServiceError):
    """Raised when file upload to S3 fails."""

    pass


class S3DeleteError(S3ServiceError):
    """Raised when file deletion from S3 fails."""

    pass


class S3ValidationError(S3ServiceError):
    """Raised when file validation fails."""

    pass


class S3Service:
    """
    Service for managing image uploads and operations with Amazon S3.
    
    This service handles:
    - File validation (type, size)
    - Unique key generation
    - Upload and deletion operations
    - URL generation
    - Error handling and logging
    
    All operations use the centralized S3Config for credentials and settings.
    """

    def __init__(self) -> None:
        """
        Initialize S3Service with AWS credentials from config.
        
        The service creates a boto3 S3 client using credentials from
        the centralized S3Config instance.
        """
        self.config = get_s3_config()
        self.s3_client = boto3.client(
            "s3",
            region_name=self.config.aws_region,
            aws_access_key_id=self.config.aws_access_key_id,
            aws_secret_access_key=self.config.aws_secret_access_key,
        )
        logger.debug(
            "S3Service initialized for bucket: %s in region: %s",
            self.config.aws_s3_bucket_name,
            self.config.aws_region,
        )

    def _generate_unique_key(
        self,
        original_filename: str,
        folder: str = "uploads",
    ) -> str:
        """
        Generate a unique S3 object key for an uploaded file.
        
        The key follows this pattern:
        {folder}/YYYY/MM/DD/{uuid}-{original_filename}
        
        Example:
            users/profiles/2026/06/08/550e8400-e29b-41d4-a716-446655440000-avatar.jpg
        
        Args:
            original_filename: Original filename provided by user
            folder: Folder prefix for organization (default: "uploads")
            
        Returns:
            str: Unique S3 object key
        """
        now = datetime.utcnow()
        unique_id = str(uuid.uuid4())
        
        # Keep original extension
        file_ext = (
            "." + original_filename.split(".")[-1]
            if "." in original_filename
            else ""
        )
        
        key = (
            f"{folder}/{now.year:04d}/{now.month:02d}/{now.day:02d}/"
            f"{unique_id}{file_ext}"
        )
        return key

    def _validate_file(
        self,
        file_content: bytes,
        filename: str,
        expected_mimetype: Optional[str] = None,
    ) -> None:
        """
        Validate uploaded file before S3 upload.
        
        Checks:
        - File size is within limits
        - File type is allowed
        - Filename is valid
        
        Args:
            file_content: Raw file bytes
            filename: Original filename
            expected_mimetype: Optional MIME type to validate against
            
        Raises:
            S3ValidationError: If file validation fails
        """
        # Check file size
        file_size = len(file_content)
        if file_size == 0:
            raise S3ValidationError("File is empty")
        if file_size > MAX_FILE_SIZE_BYTES:
            raise S3ValidationError(
                f"File size ({file_size} bytes) exceeds maximum "
                f"allowed size ({MAX_FILE_SIZE_BYTES} bytes)"
            )

        # Determine MIME type
        guessed_mimetype, _ = mimetypes.guess_type(filename)
        
        if expected_mimetype:
            if guessed_mimetype != expected_mimetype:
                logger.warning(
                    "MIME type mismatch: expected %s, got %s for file %s",
                    expected_mimetype,
                    guessed_mimetype,
                    filename,
                )
        
        # Check if file type is allowed
        if guessed_mimetype and guessed_mimetype not in ALLOWED_IMAGE_TYPES:
            raise S3ValidationError(
                f"File type '{guessed_mimetype}' is not allowed. "
                f"Allowed types: {', '.join(ALLOWED_IMAGE_TYPES)}"
            )

        logger.debug(
            "File validation passed for: %s (size: %d bytes, type: %s)",
            filename,
            file_size,
            guessed_mimetype,
        )

    def upload_file(
        self,
        file_content: bytes,
        original_filename: str,
        folder: str = "uploads",
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Upload a file to S3 and return the unique image key.
        
        The function:
        1. Validates the file (size, type)
        2. Generates a unique key
        3. Uploads to S3
        4. Returns only the key (NOT the full URL)
        
        Note: Only the image key is returned and should be stored in the database.
        The full URL can be generated later using generate_image_url().
        
        Args:
            file_content: Raw file bytes to upload
            original_filename: Original filename (used for generating the key)
            folder: S3 folder prefix for organization (default: "uploads")
            metadata: Optional metadata dict to attach to S3 object
                     (e.g., {"user_id": "123", "upload_date": "2026-06-08"})
        
        Returns:
            str: Unique image key (NOT full URL)
                Example: uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg
        
        Raises:
            S3ValidationError: If file validation fails
            S3UploadError: If upload to S3 fails
            
        Example:
            image_key = s3_service.upload_file(
                file_content=file_bytes,
                original_filename="profile.jpg",
                folder="users/profiles",
                metadata={"user_id": user.id}
            )
            # Store image_key in database, NOT the full URL
        """
        # Validate file first
        try:
            self._validate_file(file_content, original_filename)
        except S3ValidationError as e:
            logger.error("File validation failed for %s: %s", original_filename, str(e))
            raise

        image_key = self._generate_unique_key(original_filename, folder)

        s3_metadata = metadata or {}
        s3_metadata["original-filename"] = original_filename
        s3_metadata["upload-timestamp"] = datetime.utcnow().isoformat()
        try:
            self.s3_client.put_object(
                Bucket=self.config.aws_s3_bucket_name,
                Key=image_key,
                Body=file_content,
                Metadata=s3_metadata,
            )
            logger.info(
                "File uploaded successfully to S3: %s (bucket: %s)",
                image_key,
                self.config.aws_s3_bucket_name,
            )
            return image_key
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(
                "S3 upload failed for %s: [%s] %s",
                image_key,
                error_code,
                error_message,
            )
            raise S3UploadError(
                f"Failed to upload file to S3: {error_code} - {error_message}"
            ) from e

    def delete_file(self, image_key: str) -> bool:
        """
        Delete a file from S3 using its image key.
        
        Args:
            image_key: The S3 object key to delete
                      (e.g., "uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg")
        
        Returns:
            bool: True if deletion was successful
        
        Raises:
            S3ValidationError: If image_key is invalid
            S3DeleteError: If deletion from S3 fails
            
        Example:
            success = s3_service.delete_file("uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg")
            if success:
                # Also delete the record from database
                pass
        """
        # Validate image key
        try:
            validate_image_key(image_key)
        except ValueError as e:
            logger.error("Invalid image key: %s", str(e))
            raise S3ValidationError(str(e)) from e

        try:
            self.s3_client.delete_object(
                Bucket=self.config.aws_s3_bucket_name,
                Key=image_key,
            )
            logger.info(
                "File deleted successfully from S3: %s (bucket: %s)",
                image_key,
                self.config.aws_s3_bucket_name,
            )
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(
                "S3 deletion failed for %s: [%s] %s",
                image_key,
                error_code,
                error_message,
            )
            raise S3DeleteError(
                f"Failed to delete file from S3: {error_code} - {error_message}"
            ) from e

    def generate_image_url(self, image_key: str) -> str:
        """
        Generate a public image URL from an image key.
        
        This function constructs the full URL by combining the configured
        AWS_S3_BASE_URL with the image key.
        
        Args:
            image_key: The S3 object key
                      (e.g., "uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg")
        
        Returns:
            str: Full public image URL
                Example: "https://cdn.kampulynk.com/uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg"
        
        Raises:
            S3ValidationError: If image_key is invalid
            
        Example:
            # Get from database
            image_key = post_media.image_key  # "uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg"
            
            # Generate URL for API response
            url = s3_service.generate_image_url(image_key)
            # Returns: "https://cdn.kampulynk.com/uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg"
        """
        try:
            validate_image_key(image_key)
        except ValueError as e:
            logger.error("Invalid image key: %s", str(e))
            raise S3ValidationError(str(e)) from e

        base_url = self.config.aws_s3_base_url.rstrip("/")
        clean_key = image_key.lstrip("/")

        url = f"{base_url}/{clean_key}"
        return url
