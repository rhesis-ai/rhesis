"""Alembic environment configuration for Analytics Database"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables
load_dotenv()

# Add project path to sys.path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "src")))

# Import models
from processor.models import Base

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Construct database URL from environment variables.

    Uses ANALYTICS_DB_* environment variables for the dedicated analytics database.
    """
    # Try to get full URL first
    db_url = os.getenv("ANALYTICS_DATABASE_URL")
    if db_url:
        return db_url

    # Construct from analytics-specific environment variables
    user = os.getenv("ANALYTICS_DB_USER", "analytics-user")
    password = os.getenv("ANALYTICS_DB_PASS", "analytics-password")
    host = os.getenv("ANALYTICS_DB_HOST", "postgres-analytics")
    port = os.getenv("ANALYTICS_DB_PORT", "5432")
    db_name = os.getenv("ANALYTICS_DB_NAME", "rhesis-analytics")

    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    url = get_database_url()

    connectable = create_engine(
        url,
        poolclass=None,  # Disable connection pooling for migrations
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
