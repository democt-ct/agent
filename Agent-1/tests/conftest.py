"""
Test configuration and fixtures.

Uses SQLite (in-memory) for fast unit tests by default.
Override TEST_DATABASE_URL env var to use PostgreSQL for integration tests:
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5433/patient_agent_test
"""

import os
import sys
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Set test environment BEFORE importing any app modules ──
os.environ["TESTING"] = "true"
# Use file-based SQLite so the app engine (used by TestClient API tests)
# and the test engine (used by db_session unit tests) share the same database.
# In-memory SQLite gives each engine its own database, breaking cross-engine queries.
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")

import atexit

@atexit.register
def _cleanup_test_db():
    """Remove the test database file after tests complete."""
    import pathlib
    db_path = pathlib.Path("./test.db")
    if db_path.exists():
        try:
            db_path.unlink()
        except PermissionError:
            pass
    for ext in ("-wal", "-shm"):
        p = pathlib.Path(f"./test.db{ext}")
        if p.exists():
            try:
                p.unlink()
            except PermissionError:
                pass

from app.core.database import Base

# Import ALL models so they register on Base.metadata before create_all
import app.models  # noqa: F401

# Ensure tables exist on the app's module-level engine (used by TestClient)
# File-based SQLite means all engines share the same database file
from app.core.database import engine as app_engine
Base.metadata.create_all(bind=app_engine)


@pytest.fixture(scope="session")
def db_engine():
    """Create a test database engine and all tables (once per session).
    Uses the SAME database URL as the app engine for compatibility."""
    engine = create_engine(
        os.environ["DATABASE_URL"],
        echo=False,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        if "sqlite" in os.environ["DATABASE_URL"]:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Only create tables if this is a different database from the app engine
    # (for in-memory, it's always different; for file-based, it's the same)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """
    Create a fresh database session with transaction rollback.

    Each test gets a clean database state: changes are rolled back
    automatically after the test completes.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client() -> Generator:
    """Create a FastAPI TestClient using the app's own database engine."""
    from app.main import app

    with TestClient(app) as c:
        yield c


# ── Seed data helpers ──

@pytest.fixture
def sample_patient_data() -> dict:
    """Sample patient data for tests."""
    return {
        "hospital_id": "hospital-a",
        "patient_code": "TEST001",
        "full_name": "测试患者",
        "gender": "male",
        "birth_date": "1990-01-15",
        "phone": "13800138000",
        "address": "测试地址",
        "allergy_history": "青霉素过敏",
        "family_history": "父亲高血压",
        "notes": "测试患者备注",
    }


@pytest.fixture
def sample_medical_record_data() -> dict:
    """Sample medical record data for tests."""
    return {
        "record_type": "outpatient",
        "title": "测试病历",
        "department": "心内科",
        "doctor_name": "测试医生",
        "chief_complaint": "测试主诉",
        "diagnosis": "测试诊断",
        "treatment_plan": "测试治疗方案",
        "medications": "测试药物",
        "notes": "测试备注",
    }


@pytest.fixture
def sample_visit_record_data() -> dict:
    """Sample visit record data for tests."""
    return {
        "visit_type": "outpatient",
        "department": "心内科",
        "doctor_name": "测试医生",
        "campus": "本部院区",
        "chief_complaint": "测试主诉",
        "visit_status": "completed",
        "visit_summary": "测试就诊摘要",
        "follow_up_plan": "测试随访计划",
    }
