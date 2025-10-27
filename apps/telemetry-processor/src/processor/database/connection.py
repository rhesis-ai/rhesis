"""
Database Connection Management

Handles database engine creation, session management, and table initialization.
Follows the Singleton pattern for database engine management.
"""

import logging
import os
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from processor.models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections and sessions.

    Implements Singleton pattern to ensure only one engine instance exists.
    Provides methods for creating sessions and initializing tables.
    """

    _instance: Optional["DatabaseManager"] = None
    _engine: Optional[Engine] = None
    _session_maker: Optional[sessionmaker] = None

    def __new__(cls) -> "DatabaseManager":
        """Ensure only one instance exists (Singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize database connection if not already initialized."""
        if self._engine is None:
            self._initialize_engine()

    def _initialize_engine(self) -> None:
        """Create database engine from environment variables."""
        db_url = self._get_database_url()

        logger.info(f"Initializing database connection: {self._mask_url(db_url)}")

        self._engine = create_engine(
            db_url,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=10,  # Connection pool size
            max_overflow=20,  # Extra connections during high load
        )

        self._session_maker = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )

        # Create tables if they don't exist
        self._create_tables()

        logger.info("Database connection initialized successfully")

    def _get_database_url(self) -> str:
        """
        Construct database URL from environment variables.

        Returns:
            str: PostgreSQL connection URL
        """
        # Try to get full URL first
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url

        # Construct from individual parts
        user = os.getenv("SQLALCHEMY_DB_USER", "rhesis-user")
        password = os.getenv("SQLALCHEMY_DB_PASS", "your-secured-password")
        host = os.getenv("SQLALCHEMY_DB_HOST", "postgres")
        port = os.getenv("SQLALCHEMY_DB_PORT", "5432")
        db_name = os.getenv("SQLALCHEMY_DB_NAME", "rhesis-db")

        return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"

    def _mask_url(self, url: str) -> str:
        """Mask password in database URL for logging."""
        if "@" in url and ":" in url:
            parts = url.split("@")
            if len(parts) == 2:
                credentials = parts[0].split("://")
                if len(credentials) == 2:
                    protocol = credentials[0]
                    user_pass = credentials[1].split(":")
                    if len(user_pass) == 2:
                        return f"{protocol}://{user_pass[0]}:***@{parts[1]}"
        return url

    def _create_tables(self) -> None:
        """Create all tables defined in models if they don't exist."""
        try:
            Base.metadata.create_all(self._engine)
            logger.info("Database tables verified/created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}", exc_info=True)
            raise

    def get_session(self) -> Session:
        """
        Create a new database session.

        Returns:
            Session: SQLAlchemy session for database operations
        """
        if self._session_maker is None:
            raise RuntimeError("Database not initialized")
        return self._session_maker()

    def get_engine(self) -> Engine:
        """
        Get the database engine.

        Returns:
            Engine: SQLAlchemy engine
        """
        if self._engine is None:
            raise RuntimeError("Database not initialized")
        return self._engine

    def close(self) -> None:
        """Close all database connections."""
        if self._engine:
            self._engine.dispose()
            logger.info("Database connections closed")


# Global instance accessor
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """
    Get the global DatabaseManager instance.

    Returns:
        DatabaseManager: Singleton database manager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
