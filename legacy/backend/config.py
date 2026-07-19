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
    # Environment
    ENVIRONMENT: str = "development"

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

    # Google OAuth settings
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    class Config:
        env_file = "../.env"
        env_file_encoding = 'utf-8'

settings = Settings()

# Debug: Print loaded settings
print(f"Loaded settings:")
print(f"ENVIRONMENT: {settings.ENVIRONMENT}")
print(f"DATABASE_URL: {settings.DATABASE_URL}")
print(f"ANTHROPIC_API_KEY: {'*' * len(settings.ANTHROPIC_API_KEY)}")  # Don't print the actual key
print(f"SECRET_KEY: {'*' * len(settings.SECRET_KEY)}")  # Don't print the actual key
print(f"GOOGLE_CLIENT_ID: {'*' * len(settings.GOOGLE_CLIENT_ID)}")  # Don't print the actual ID
print(f"GOOGLE_CLIENT_SECRET: {'*' * len(settings.GOOGLE_CLIENT_SECRET)}")  # Don't print the actual secret