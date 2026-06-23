"""
Production configuration for the application.
This file contains production-specific settings.
"""

import os


# Database configuration
DATABASE_CONFIG = {
    "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
    "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
    "pool_pre_ping": True,
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
}

# Redis configuration
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")),
    "password": os.getenv("REDIS_PASSWORD", None),
    "socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
    "socket_connect_timeout": int(os.getenv("REDIS_CONNECT_TIMEOUT", "5")),
    "retry_on_timeout": True,
}

# Session configuration
SESSION_CONFIG = {
    "cache_ttl": int(os.getenv("SESSION_CACHE_TTL", "86400")),  # 24 hours
    "max_sessions_per_user": int(os.getenv("MAX_SESSIONS_PER_USER", "10")),
}

# Logging configuration
LOGGING_CONFIG = {
    "level": os.getenv("LOG_LEVEL", "INFO"),
    "format": os.getenv("LOG_FORMAT", "text"),  # "text" or "json"
    "file": os.getenv("LOG_FILE", None),
}

# Security configuration
SECURITY_CONFIG = {
    "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
    "rate_limit_per_minute": int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    "max_request_size": int(os.getenv("MAX_REQUEST_SIZE", "10485760")),  # 10MB
}

# Application configuration
APP_CONFIG = {
    "version": "0.3.0",
    "debug": os.getenv("DEBUG", "false").lower() == "true",
    "workers": int(os.getenv("WORKERS", "1")),
}