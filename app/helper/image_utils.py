"""
Image utility functions for URL generation and validation.

This module provides helper functions for:
- Generating public URLs from image keys
- Validating image keys
- Image key format specifications

Image keys follow this convention:
{folder}/YYYY/MM/DD/{uuid}.{ext}

Example:
    uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg
    users/profiles/2026/06/08/550e8400-e29b-41d4-a716-446655440000.png
    posts/media/2026/06/08/550e8400-e29b-41d4-a716-446655440000.webp
"""

import logging
import re

from .config import get_s3_config

logger = logging.getLogger(__name__)

# Pattern for valid image keys
# Allows: alphanumeric, hyphens, underscores, forward slashes, and dots
IMAGE_KEY_PATTERN = r"^[a-zA-Z0-9/_\-\.]+$"

# UUID pattern (simplified)
UUID_PATTERN = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"

# Allowed image extensions
ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
}


def validate_image_key(image_key: str) -> bool:
    """
    Validate that an image key has the correct format.
    
    Validation checks:
    - Key is not empty
    - Key contains only allowed characters (alphanumeric, slashes, hyphens, dots, underscores)
    - Key has a valid file extension
    - Key doesn't contain suspicious patterns (e.g., path traversal)
    
    Args:
        image_key: The image key to validate
                  (e.g., "uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg")
    
    Returns:
        bool: True if key is valid
    
    Raises:
        ValueError: If key is invalid, with descriptive error message
        
    Example:
        try:
            validate_image_key("uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg")
            print("Valid image key")
        except ValueError as e:
            print(f"Invalid key: {e}")
    """
    if not image_key:
        raise ValueError("Image key cannot be empty")

    if not isinstance(image_key, str):
        raise ValueError(f"Image key must be a string, got {type(image_key).__name__}")

    if len(image_key) > 500:
        raise ValueError(f"Image key is too long ({len(image_key)} chars, max 500)")

    # Check for path traversal attempts
    if ".." in image_key:
        raise ValueError("Image key contains invalid path traversal pattern (..).")

    # Check for suspicious patterns
    if image_key.startswith("/"):
        raise ValueError("Image key should not start with /")

    # Check allowed characters
    if not re.match(IMAGE_KEY_PATTERN, image_key):
        raise ValueError(
            f"Image key contains invalid characters. "
            f"Allowed: alphanumeric, /, -, _, . Got: {image_key}"
        )

    # Check file extension
    extension = None
    if "." in image_key:
        extension = "." + image_key.split(".")[-1].lower()

    if not extension:
        raise ValueError("Image key must have a file extension")

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"Image extension '{extension}' is not allowed. "
            f"Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    return True


def generate_image_url(image_key: str) -> str:
    """
    Generate a full public image URL from an image key.
    
    This is a convenience function that combines the S3 base URL
    from configuration with the image key.
    
    The generated URL can be used in API responses to clients.
    
    Args:
        image_key: The S3 object key (NOT a full URL)
                  Example: "uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg"
    
    Returns:
        str: Full public image URL
            Example: "https://cdn.kampulynk.com/uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg"
    
    Raises:
        ValueError: If image_key is invalid
        
    Example:
        # Database stores only the key
        db_image_key = "users/profiles/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg"
        
        # Generate URL for API response
        url = generate_image_url(db_image_key)
        # "https://cdn.kampulynk.com/users/profiles/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg"
        
        # Return in response
        return {
            "id": user.id,
            "name": user.name,
            "profile_photo_url": url  # Full URL sent to client
        }
    """
    # Validate the image key first
    validate_image_key(image_key)

    # Get S3 configuration
    config = get_s3_config()

    # Construct the URL
    base_url = config.aws_s3_base_url.rstrip("/")
    clean_key = image_key.lstrip("/")
    
    url = f"{base_url}/{clean_key}"
    return url


def get_image_key_from_url(url: str) -> str | None:
    """
    Extract the image key from a full image URL.
    
    This is useful for extracting the key when you have a full URL
    from the database or client request.
    
    Args:
        url: Full image URL (e.g., "https://cdn.kampulynk.com/uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg")
    
    Returns:
        str | None: The image key, or None if URL doesn't match the pattern
        
    Example:
        url = "https://cdn.kampulynk.com/uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg"
        key = get_image_key_from_url(url)
        # "uploads/2026/06/08/550e8400-e29b-41d4-a716-446655440000.jpg"
    """
    if not url:
        return None

    try:
        config = get_s3_config()
        base_url = config.aws_s3_base_url.rstrip("/")

        # Check if URL starts with the base URL
        if not url.startswith(base_url):
            logger.warning(
                "URL does not match configured base URL. URL: %s, Base: %s",
                url,
                base_url,
            )
            return None

        # Extract the key by removing the base URL
        key = url[len(base_url):].lstrip("/")

        # Validate extracted key
        try:
            validate_image_key(key)
            return key
        except ValueError:
            logger.warning("Extracted key is invalid: %s", key)
            return None

    except Exception as e:
        logger.error("Error extracting image key from URL: %s", str(e))
        return None
