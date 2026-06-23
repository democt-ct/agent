import os
import time

from dotenv import load_dotenv
load_dotenv()
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from sqlalchemy.orm import declarative_base
except ImportError:  # SQLAlchemy < 1.4
    from sqlalchemy.ext.declarative import declarative_base


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# PostgreSQL configuration
# Priority: environment variable > default
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "postgres")
PG_DATABASE = os.getenv("PG_DATABASE", "patient_agent")

# Build PostgreSQL connection string
DEFAULT_PG_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DATABASE}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_PG_URL)

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

# Warn if default credentials are used in non-testing environment
if not _IS_SQLITE and PG_PASSWORD == "postgres" and os.getenv("TESTING") != "true":
    import warnings
    warnings.warn(
        "使用默认 PostgreSQL 密码 'postgres'，仅适用于开发环境。"
        "生产环境请通过 .env 或环境变量设置 PG_PASSWORD。"
    )


def _wait_for_postgres(max_wait: float = 30.0) -> None:
    """Wait for PostgreSQL to accept connections, with exponential backoff.

    Docker containers may report 'running' before postgres is ready to
    accept connections (especially on Windows/macOS).  This function
    probes the TCP port so the engine creation doesn't immediately fail.
    Only called when using PostgreSQL.
    """
    if _IS_SQLITE:
        return

    import socket

    deadline = time.monotonic() + max_wait
    delay = 0.5
    while time.monotonic() < deadline:
        try:
            sock = socket.create_connection(
                (PG_HOST, int(PG_PORT)),
                timeout=min(delay, 3.0),
            )
            sock.close()
            return  # port is open
        except OSError:
            time.sleep(delay)
            delay = min(delay * 1.5, 5.0)  # exponential backoff, cap at 5s

    # Last attempt — let SQLAlchemy give the final error
    return


_wait_for_postgres()

# Create engine — pool arguments are PG-specific, skip for SQLite
if _IS_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
