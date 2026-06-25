from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine

from rhesis.backend.app.config.settings import get_database_settings
from rhesis.backend.app.models import Base

# Eagerly import EE-owned ORM models when the EE package is installed so
# their tables join Base.metadata before Alembic configures the migration
# context. Without this, autogenerate would not see EE tables and an
# offline ``alembic upgrade`` from a fresh DB would leave them missing.
# The import is wrapped because a Community-only install must keep
# working unchanged (no rhesis.backend.ee package on sys.path).
try:
    import rhesis.backend.ee.api_clients.clients  # noqa: F401
except ImportError:
    pass

try:
    import rhesis.backend.ee.rbac.models  # noqa: F401
except ImportError:
    pass

# load environment variables
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.

fileConfig(config.config_file_name)

# Import your models here to ensure they are known to Alembic
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# my_important_option = config.get_main_option("my_important_option")


def include_object(obj, name, type_, reflected, compare_to):
    """Exclude DB views (managed by explicit migrations) from autogenerate."""
    if type_ == "table" and getattr(obj, "info", {}).get("is_view"):
        return False
    return True


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_settings().admin_url

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = get_database_settings().admin_url

    connectable = create_engine(url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=False,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
