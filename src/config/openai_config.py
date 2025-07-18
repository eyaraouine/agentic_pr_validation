# OpenAI Configuration for Azure OpenAI support

import os
from typing import Optional
import openai
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from src.config.settings import Settings
from src.utils.logger import setup_logger

logger = setup_logger("config.openai")
settings = Settings()


def configure_openai():
    """
    Configure OpenAI to use either standard OpenAI or Azure OpenAI
    based on environment configuration
    """

    # Check if using Azure OpenAI
    if settings.OPENAI_API_TYPE == "azure":
        logger.info("Configuring Azure OpenAI...")

        # Validate Azure OpenAI settings
        if not all([
            settings.AZURE_OPENAI_API_KEY,
            settings.AZURE_OPENAI_ENDPOINT,
            settings.AZURE_OPENAI_DEPLOYMENT_NAME
        ]):
            raise ValueError(
                "Azure OpenAI requires AZURE_OPENAI_API_KEY, "
                "AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_NAME"
            )


        # Set environment variables for CrewAI
        os.environ["AZURE_OPENAI_API_KEY"] = settings.AZURE_OPENAI_API_KEY
        os.environ["AZURE_OPENAI_ENDPOINT"] = settings.AZURE_OPENAI_ENDPOINT
        os.environ["AZURE_OPENAI_API_VERSION"] = settings.AZURE_OPENAI_API_VERSION
        os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"] = settings.AZURE_OPENAI_DEPLOYMENT_NAME

        logger.info(f"Azure OpenAI configured with endpoint: {settings.AZURE_OPENAI_ENDPOINT}")
        logger.info(f"Using deployment: {settings.AZURE_OPENAI_DEPLOYMENT_NAME}")

    else:
        # Standard OpenAI configuration
        logger.info("Configuring standard OpenAI...")

        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for standard OpenAI")

        openai.api_key = settings.OPENAI_API_KEY
        os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

        logger.info("Standard OpenAI configured")


def get_llm_config() -> dict:
    """
    Get LLM configuration for CrewAI agents
    """
    if settings.OPENAI_API_TYPE == "azure":
        return {
            "model": settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            "api_type": "azure",
            "api_key": settings.AZURE_OPENAI_API_KEY,
            "api_base": settings.AZURE_OPENAI_ENDPOINT,
            "api_version": settings.AZURE_OPENAI_API_VERSION,
            "deployment_name": settings.AZURE_OPENAI_DEPLOYMENT_NAME
        }
    else:
        return {
            "model": "gpt-4",  # or "gpt-3.5-turbo"
            "api_key": settings.OPENAI_API_KEY
        }


def get_llm_instance():
    """Create and return an LLM instance (not just config)"""

    return AzureChatOpenAI(
        azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        temperature=settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS
    )


# Initialize OpenAI configuration when module is imported
configure_openai()