"""
Configuration module for the LLM-powered personal assistant.

This module uses Pydantic's BaseSettings to manage environment variables
and configuration settings for the application.
"""

from pydantic import BaseSettings


class Settings(BaseSettings):
    """
    Application settings.

    These settings are loaded from environment variables or .env file.
    """
    # Database settings
    DATABASE_URL: str = "sqlite:///./test.db"

    # Anthropic API settings
    ANTHROPIC_API_KEY: str

    # CORS settings
    CORS_ORIGINS: list[str] = ["http://localhost", "http://localhost:3000"]

    # JWT settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"


settings = Settings()