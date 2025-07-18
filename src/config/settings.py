# Configuration Settings

from pydantic_settings import BaseSettings
from pydantic import Field, validator, model_validator
from typing import List, Optional, Dict, Any
import os
from pathlib import Path


class Settings(BaseSettings):
    """
    Application settings with environment variable support
    """

    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="API_PORT")
    API_VERSION: str = Field(default="1.0.0", env="API_VERSION")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")

    # Security
    API_KEY: str = Field(..., env="API_KEY")
    API_KEY_HEADER: str = Field(default="X-API-Key", env="API_KEY_HEADER")
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "https://dev.azure.com"],
        env="ALLOWED_ORIGINS"
    )

    # Azure DevOps Configuration
    AZURE_DEVOPS_PAT: str = Field(..., env="AZURE_DEVOPS_PAT")
    AZURE_DEVOPS_ORG: Optional[str] = Field(None, env="AZURE_DEVOPS_ORG")
    POST_RESULTS_TO_PR: bool = Field(default=True, env="POST_RESULTS_TO_PR")

    # CrewAI Configuration
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    CREW_VERBOSE: bool = Field(default=True, env="CREW_VERBOSE")
    AGENT_MAX_ITERATIONS: int = Field(default=5, env="AGENT_MAX_ITERATIONS")
    MANAGER_MAX_ITERATIONS: int = Field(default=10, env="MANAGER_MAX_ITERATIONS")
    MAX_RPM: int = Field(default=20, env="MAX_RPM")

    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY: Optional[str] = Field(None, env="AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT: Optional[str] = Field(None, env="AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_DEPLOYMENT_NAME: Optional[str] = Field(None, env="AZURE_OPENAI_DEPLOYMENT_NAME")
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-02-15-preview", env="AZURE_OPENAI_API_VERSION")
    OPENAI_API_TYPE: Optional[str] = Field(None, env="OPENAI_API_TYPE")

    # Embedder Configuration
    EMBEDDER_PROVIDER: str = Field(default="openai", env="EMBEDDER_PROVIDER")
    EMBEDDER_MODEL: str = Field(default="text-embedding-3-small", env="EMBEDDER_MODEL")

    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    LOG_FILE: Optional[str] = Field(None, env="LOG_FILE")

    # Validation Configuration
    VALIDATION_TIMEOUT: int = Field(default=600, env="VALIDATION_TIMEOUT")  # seconds
    SKIP_NON_APPLICABLE_CHECKS: bool = Field(default=True, env="SKIP_NON_APPLICABLE_CHECKS")

    # File Analysis Configuration
    MAX_FILE_SIZE_MB: int = Field(default=10, env="MAX_FILE_SIZE_MB")
    SUPPORTED_FILE_EXTENSIONS: List[str] = Field(
        default=[".json", ".py", ".scala", ".sql", ".r", ".yaml", ".yml"],
        env="SUPPORTED_FILE_EXTENSIONS"
    )

    # Checkpoint Configuration
    CHECKPOINTS_CONFIG_PATH: str = Field(
        default="src/config/checkpoints.yaml",
        env="CHECKPOINTS_CONFIG_PATH"
    )

    # Cache Configuration
    ENABLE_CACHE: bool = Field(default=True, env="ENABLE_CACHE")
    CACHE_TTL: int = Field(default=3600, env="CACHE_TTL")  # seconds

    # Database Configuration (for job tracking)
    DATABASE_URL: Optional[str] = Field(None, env="DATABASE_URL")
    USE_IN_MEMORY_JOBS: bool = Field(default=True, env="USE_IN_MEMORY_JOBS")

    # Notification Configuration
    TEAMS_WEBHOOK_URL: Optional[str] = Field(None, env="TEAMS_WEBHOOK_URL")
    SLACK_WEBHOOK_URL: Optional[str] = Field(None, env="SLACK_WEBHOOK_URL")
    EMAIL_NOTIFICATIONS_ENABLED: bool = Field(default=False, env="EMAIL_NOTIFICATIONS_ENABLED")

    # Performance Configuration
    ENABLE_PROFILING: bool = Field(default=False, env="ENABLE_PROFILING")
    ENABLE_METRICS: bool = Field(default=True, env="ENABLE_METRICS")
    METRICS_PORT: int = Field(default=9090, env="METRICS_PORT")



    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment"""
        valid_envs = ["development", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"Invalid environment. Must be one of: {valid_envs}")
        return v.lower()

    @validator("CHECKPOINTS_CONFIG_PATH")
    def validate_checkpoints_path(cls, v):
        """Validate checkpoints config file exists"""
        path = Path(v)
        if not path.exists():
            # Try relative to project root
            project_root = Path(__file__).parent.parent.parent
            path = project_root / v
            if not path.exists():
                raise ValueError(f"Checkpoints config file not found: {v}")
        return str(path)

    @model_validator(mode='after')
    def validate_openai_configuration(self) -> 'Settings':
        """Validate OpenAI configuration after all fields are set"""
        if self.OPENAI_API_TYPE == "azure":
            # Azure OpenAI validation
            if not self.AZURE_OPENAI_API_KEY:
                raise ValueError("AZURE_OPENAI_API_KEY is required when OPENAI_API_TYPE is 'azure'")
            if not self.AZURE_OPENAI_ENDPOINT:
                raise ValueError("AZURE_OPENAI_ENDPOINT is required when OPENAI_API_TYPE is 'azure'")
            if not self.AZURE_OPENAI_DEPLOYMENT_NAME:
                raise ValueError("AZURE_OPENAI_DEPLOYMENT_NAME is required when OPENAI_API_TYPE is 'azure'")

            # Validate endpoint format
            if self.AZURE_OPENAI_ENDPOINT:
                if not self.AZURE_OPENAI_ENDPOINT.startswith("https://"):
                    raise ValueError("AZURE_OPENAI_ENDPOINT must start with https://")
                if not self.AZURE_OPENAI_ENDPOINT.endswith("/"):
                    raise ValueError("AZURE_OPENAI_ENDPOINT must end with /")
        else:
            # Standard OpenAI validation
            if not self.OPENAI_API_KEY:
                raise ValueError(
                    "Either set OPENAI_API_KEY for standard OpenAI or "
                    "set OPENAI_API_TYPE=azure with Azure OpenAI credentials"
                )

        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

        # Allow extra fields for forward compatibility
        extra = "allow"


# Singleton instance
_settings = None


def get_settings() -> Settings:
    """Get cached settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Environment-specific settings overrides
class DevelopmentSettings(Settings):
    """Development environment settings"""
    CREW_VERBOSE: bool = True
    LOG_LEVEL: str = "DEBUG"
    ENABLE_PROFILING: bool = True


class ProductionSettings(Settings):
    """Production environment settings"""
    CREW_VERBOSE: bool = False
    LOG_LEVEL: str = "INFO"
    ENABLE_PROFILING: bool = False
    USE_IN_MEMORY_JOBS: bool = False


def get_environment_settings() -> Settings:
    """Get environment-specific settings"""
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env == "development":
        return DevelopmentSettings()
    elif env == "production":
        return ProductionSettings()
    else:
        return Settings()