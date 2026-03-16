# app/config.py
"""
Application configuration.
"""
from pathlib import Path
import json
from pydantic_settings import BaseSettings  # Changed from pydantic
from pydantic import ConfigDict, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Look for .env in backend root, not in app/
    model_config = ConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Application
    APP_NAME: str = "CyberDuel Protocol"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///./data/cyberduel.db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_SECRET: str = "your-jwt-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed.startswith("[") and trimmed.endswith("]"):
                return json.loads(trimmed)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value
    
    # Oracle
    ORACLE_PROVIDER: str = "mock"  # "mock" or "pandascore"
    ORACLE_API_KEY: str = ""  # API key for external providers
    ORACLE_POLL_INTERVAL_MINUTES: int = 5  # How often to check for results
    
    # Demo user
    DEMO_INITIAL_BALANCE: float = 1000.00


settings = Settings()