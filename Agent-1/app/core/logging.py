"""
Structured logging configuration for the application.
"""

import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data
        
        return json.dumps(log_entry, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Text log formatter for human-readable output."""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        message = record.getMessage()
        
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return f"[{timestamp}] {record.levelname:8s} {record.name}: {message}"


def setup_logging(
    level: str = "INFO",
    format_type: str = "text",
    log_file: str = None,
) -> None:
    """
    Set up structured logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ("text" or "json")
        log_file: Optional log file path
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatter
    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logging.info(f"Logging initialized: level={level}, format={format_type}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


# Request logging middleware helper
def log_request(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    client_ip: str = None,
) -> None:
    """Log HTTP request details."""
    extra_data = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
    }
    if client_ip:
        extra_data["client_ip"] = client_ip
    
    log_record = logging.LogRecord(
        name="access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"{method} {path} {status_code} {duration_ms:.2f}ms",
        args=(),
        exc_info=None,
    )
    log_record.extra_data = extra_data
    
    if status_code >= 500:
        logger.log(logging.ERROR, log_record.msg, extra={"extra_data": extra_data})
    elif status_code >= 400:
        logger.log(logging.WARNING, log_record.msg, extra={"extra_data": extra_data})
    else:
        logger.log(logging.INFO, log_record.msg, extra={"extra_data": extra_data})