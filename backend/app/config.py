# app/config.py
"""
Application configuration.
"""
from pydantic_settings import BaseSettings  # Changed from pydantic
from pydantic import ConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = ConfigDict(env_file=".env")
    
    # Application
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "sqlite:///./cyberduel.db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]
    
    # Oracle
    ORACLE_PROVIDER: str = "mock"  # "mock" or "pandascore"
    ORACLE_API_KEY: str = ""  # API key for external providers
    ORACLE_POLL_INTERVAL_MINUTES: int = 5  # How often to check for results
    
    # Demo user
    DEMO_INITIAL_BALANCE: float = 1000.00


settings = Settings()