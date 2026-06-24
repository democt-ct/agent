from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Photo Agent"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: Optional[str] = None
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # File upload
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # AI Model settings
    VISION_MODEL: str = "qwen-vl"
    EDITING_MODEL: str = "opencv"
    
    # ModelScope Configuration
    MODELSCOPE_API_TOKEN: Optional[str] = None
    MODELSCOPE_MODEL_ID: str = "Qwen/Qwen-VL-Chat"
    
    CORS_ORIGINS: str = '["http://localhost:3000"]'

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()