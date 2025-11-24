import os
import re
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

from rhesis.backend.app.models import Base

# load environment variables
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.

fileConfig(config.config_file_name)

# Add your project's path to the sys.path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "app")))

# Import your models here to ensure they are known to Alembic
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# my_important_option = config.get_main_option("my_important_option")


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = os.environ.get("SQLALCHEMY_DATABASE_URL", "")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url_tokens = {
        "SQLALCHEMY_DB_DRIVER": os.getenv("SQLALCHEMY_DB_DRIVER", ""),
        "SQLALCHEMY_DB_USER": os.getenv("SQLALCHEMY_DB_USER", ""),
        "SQLALCHEMY_DB_PASS": os.getenv("SQLALCHEMY_DB_PASS", ""),
        "SQLALCHEMY_DB_HOST": os.getenv("SQLALCHEMY_DB_HOST", ""),
        "SQLALCHEMY_DB_NAME": os.getenv("SQLALCHEMY_DB_NAME", ""),
    }

    # Get the base URL from config
    url = config.get_main_option("sqlalchemy.url")

    # If we're running locally with Cloud SQL Proxy
    if os.getenv("SQLALCHEMY_DB_HOST", "").startswith(("/cloudsql", "/tmp/cloudsql")):
        # Modify the connection string for local Unix socket
        unix_socket = os.getenv("SQLALCHEMY_DB_HOST")
        url = f"postgresql://{url_tokens['SQLALCHEMY_DB_USER']}:{url_tokens['SQLALCHEMY_DB_PASS']}@/{url_tokens['SQLALCHEMY_DB_NAME']}?host={unix_socket}"
    else:
        # Use the standard URL substitution for other environments
        url = re.sub(r"\${(.+?)}", lambda m: url_tokens[m.group(1)], url)

    # if we are running tests, use the test database instead
    if os.getenv("SQLALCHEMY_DB_MODE") == "test":
        url = os.getenv("SQLALCHEMY_DATABASE_TEST_URL", "sqlite:///./test.db")

    connectable = create_engine(url)

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
