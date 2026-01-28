"""
Application configuration.
Uses environment variables with sensible defaults for development.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings.
    
    For development: uses SQLite by default
    For production: set DATABASE_URL to PostgreSQL connection string
    """
    
    # Application
    APP_NAME: str = "CyberDuel Protocol"
    DEBUG: bool = True
    
    # Database
    # Default: SQLite for development
    # Production: postgresql://user:password@localhost:5432/cyberduel
    DATABASE_URL: str = "sqlite:///./cyberduel.db"
    
    # Security
    JWT_SECRET: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()