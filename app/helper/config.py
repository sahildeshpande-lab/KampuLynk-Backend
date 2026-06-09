"""
S3 Configuration management using Pydantic BaseSettings.

This module provides centralized AWS S3 configuration that:
- Loads all values from environment variables
- Never hardcodes credentials
- Supports multiple environments (local, staging, production)
- Validates configuration on startup
- Provides runtime access to S3 settings

Environment Variables:
    AWS_REGION: AWS region (default: us-east-1)
    AWS_ACCESS_KEY_ID: AWS access key for authentication
    AWS_SECRET_ACCESS_KEY: AWS secret access key for authentication
    AWS_S3_BUCKET_NAME: S3 bucket name
    AWS_S3_BASE_URL: CDN base URL for public image access
    APP_ENV: Environment name (local, staging, production) - optional

Example:
    AWS_REGION=us-east-1
    AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
    AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    AWS_S3_BUCKET_NAME=kampulynk-images-prod
    AWS_S3_BASE_URL=https://cdn.kampulynk.com
    APP_ENV=production
"""

import logging
from typing import Literal

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class S3Config(BaseSettings):
    """
    Centralized S3 configuration loaded from environment variables.
    
    All AWS credentials and settings are loaded from the environment.
    This ensures credentials are never committed to version control.
    """

    # Environment identification
    app_env: Literal["local", "staging", "production"] = "local"

    # AWS S3 Configuration
    aws_region: str = "us-east-1"
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_s3_bucket_name: str
    aws_s3_base_url: str

    class Config:
        """Pydantic configuration."""

        # Load from .env file
        env_file = ".env"
        env_file_encoding = "utf-8"
        
        # Support case-insensitive environment variable loading
        case_sensitive = False

    def __init__(self, **data):
        """
        Initialize S3Config with validation.
        
        Raises:
            ValueError: If required AWS credentials are missing.
        """
        super().__init__(**data)
        self._validate_config()

    def _validate_config(self) -> None:
        """
        Validate S3 configuration.
        
        Checks:
        - All required fields are set
        - AWS credentials are not placeholder values
        - S3 bucket name and base URL are valid
        
        Raises:
            ValueError: If validation fails.
        """
        # Check for placeholder values
        placeholder_values = {
            "YOUR_AWS_REGION",
            "YOUR_AWS_ACCESS_KEY_ID",
            "YOUR_AWS_SECRET_ACCESS_KEY",
            "YOUR_S3_BUCKET_NAME",
            "YOUR_CDN_BASE_URL",
        }

        if self.aws_region in placeholder_values:
            raise ValueError(
                f"AWS_REGION is not configured: {self.aws_region}. "
                "Update your .env file with actual AWS credentials."
            )

        if self.aws_access_key_id in placeholder_values:
            raise ValueError(
                "AWS_ACCESS_KEY_ID is not configured. "
                "Update your .env file with actual AWS credentials."
            )

        if self.aws_secret_access_key in placeholder_values:
            raise ValueError(
                "AWS_SECRET_ACCESS_KEY is not configured. "
                "Update your .env file with actual AWS credentials."
            )

        if self.aws_s3_bucket_name in placeholder_values:
            raise ValueError(
                f"AWS_S3_BUCKET_NAME is not configured: {self.aws_s3_bucket_name}. "
                "Update your .env file with your actual S3 bucket name."
            )

        if self.aws_s3_base_url in placeholder_values:
            raise ValueError(
                f"AWS_S3_BASE_URL is not configured: {self.aws_s3_base_url}. "
                "Update your .env file with your actual CDN base URL."
            )

        # Validate URL format
        if not self.aws_s3_base_url.startswith(("http://", "https://")):
            raise ValueError(
                f"AWS_S3_BASE_URL must start with http:// or https://. Got: {self.aws_s3_base_url}"
            )

        logger.info(
            "S3 configuration loaded successfully for environment: %s",
            self.app_env,
        )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.app_env == "staging"

    @property
    def is_local(self) -> bool:
        """Check if running in local environment."""
        return self.app_env == "local"


# Global S3 config instance
# Lazy load only when needed
_s3_config: S3Config | None = None


def get_s3_config() -> S3Config:
    """
    Get the global S3Config instance.
    
    This function implements lazy initialization of the S3 configuration.
    Configuration is loaded from environment variables and validated on first access.
    
    Returns:
        S3Config: The global S3 configuration instance.
        
    Raises:
        ValueError: If S3 configuration is invalid.
        
    Example:
        from app.helper.config import get_s3_config
        
        config = get_s3_config()
        bucket = config.aws_s3_bucket_name
        region = config.aws_region
    """
    global _s3_config
    if _s3_config is None:
        _s3_config = S3Config()
    return _s3_config
