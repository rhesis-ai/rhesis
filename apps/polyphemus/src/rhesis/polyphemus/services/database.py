import os
from contextlib import contextmanager
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def get_database_url() -> str:
    """Get the database URL from environment variables."""
    # Try full connection string first
    db_url = os.getenv("SQLALCHEMY_DATABASE_URL")
    if db_url:
        return db_url

    # Fallback to component-based construction
    user = os.getenv("SQLALCHEMY_DB_USER", "")
    password = os.getenv("SQLALCHEMY_DB_PASS", "")
    host = os.getenv("SQLALCHEMY_DB_HOST", "")
    db_name = os.getenv("SQLALCHEMY_DB_NAME", "")

    # Handle Cloud SQL Unix socket connections
    if host and host.startswith(("/cloudsql", "/tmp/cloudsql")):
        return f"postgresql://{user}:{password}@/{db_name}?host={host}"

    # Default to localhost TCP connection
    return f"postgresql://{user}:{password}@localhost:5432/{db_name}"


SQLALCHEMY_DATABASE_URL = get_database_url()

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "connect_timeout": 10,
        "application_name": "rhesis-polyphemus",
    },
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.
    Use with 'with' statement to ensure proper cleanup.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
