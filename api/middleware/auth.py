# Authentication Middleware

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from typing import Optional

from src.config.settings import Settings
from src.utils.logger import setup_logger

settings = Settings()
logger = setup_logger("api.middleware.auth")

# API Key header configuration
api_key_header = APIKeyHeader(
    name=settings.API_KEY_HEADER,
    auto_error=False
)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """
    Verify API key from request header

    Args:
        api_key: API key from header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not api_key:
        logger.warning("API request without API key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key required"
        )

    # In production, you might want to check against a database or cache
    if api_key != settings.API_KEY:
        logger.warning(f"Invalid API key attempt: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )

    logger.debug("API key validated successfully")
    return api_key


async def get_optional_api_key(api_key: Optional[str] = Security(api_key_header)) -> Optional[str]:
    """
    Get API key if provided (for optional authentication endpoints)

    Args:
        api_key: API key from header

    Returns:
        API key if valid, None otherwise
    """
    if api_key and api_key == settings.API_KEY:
        return api_key
    return None