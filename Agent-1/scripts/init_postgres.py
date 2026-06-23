"""
PostgreSQL initialization script.
This script creates the database and all required tables.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def get_default_connection_params():
    """Get connection parameters from environment variables."""
    return {
        "host": os.getenv("PG_HOST", "localhost"),
        "port": os.getenv("PG_PORT", "5432"),
        "user": os.getenv("PG_USER", "postgres"),
        "password": os.getenv("PG_PASSWORD", "postgres"),
    }


def create_database_if_not_exists():
    """Create the database if it doesn't exist."""
    db_name = os.getenv("PG_DATABASE", "patient_agent")
    params = get_default_connection_params()
    
    try:
        conn = psycopg2.connect(**params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,)
        )
        exists = cursor.fetchone()
        
        if not exists:
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f"✓ Database '{db_name}' created successfully")
        else:
            print(f"✓ Database '{db_name}' already exists")
        
        cursor.close()
        conn.close()
        return True
    except psycopg2.Error as e:
        print(f"✗ Failed to create database: {e}")
        return False


def create_tables():
    """Create all required tables."""
    from app.core.database import engine, Base
    from app.models import (
        Patient,
        MedicalRecord,
        VisitRecord,
        MemoryConversationMessage,
        MemorySessionBufferMessage,
        MemoryBusinessProfile,
        MemoryConversationProfile,
        MemoryUserProfile,
        MemoryKeyEvent,
        MemoryPreference,
        MemoryKnowledgeChunk,
    )
    
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ All tables created successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to create tables: {e}")
        return False


def main():
    """Main initialization function."""
    print("=" * 50)
    print("PostgreSQL Initialization Script")
    print("=" * 50)
    
    print("\n1. Creating database...")
    if not create_database_if_not_exists():
        print("\n✗ Initialization failed")
        return False
    
    print("\n2. Creating tables...")
    if not create_tables():
        print("\n✗ Initialization failed")
        return False
    
    print("\n" + "=" * 50)
    print("✓ Initialization completed successfully!")
    print("=" * 50)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)