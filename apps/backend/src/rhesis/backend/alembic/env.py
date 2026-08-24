import logging
import os
import time
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

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

logger = logging.getLogger("alembic.runtime.migration")

# Session-scoped Postgres advisory lock that serializes concurrent schema
# upgrades across replicas (every backend replica runs ``migrate.sh`` at
# container start). Without it, simultaneous rollouts rely on row-level lock
# serialization inside Postgres plus idempotent migration guards to avoid
# corrupting each other.
#
# The key is a fixed constant so every replica agrees on the same lock; it is
# derived from crc32(b"rhesis-backend-migrations") = 1260693429 and must not
# change once deployments exist.
MIGRATION_ADVISORY_LOCK_KEY = 1260693429

# How long a process waits for another replica's upgrade before failing.
MIGRATION_LOCK_TIMEOUT_SECONDS = float(os.environ.get("ALEMBIC_LOCK_TIMEOUT", "600"))
LOCK_POLL_INTERVAL_SECONDS = 1.0


def _try_acquire_migration_advisory_lock(connection) -> bool:
    """Attempt a non-blocking acquisition of the migration advisory lock."""
    return bool(
        connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": MIGRATION_ADVISORY_LOCK_KEY},
        ).scalar_one()
    )


def _acquire_migration_advisory_lock(connectable):
    """Hold a Postgres advisory lock for the duration of an online upgrade.

    Uses a dedicated autocommit connection so the session-scoped lock stays
    held while Alembic runs its own transactions on the migration connection.

    Returns the connection holding the lock, or None when locking does not
    apply (non-PostgreSQL database). Raises RuntimeError if another holder
    keeps the lock beyond ``ALEMBIC_LOCK_TIMEOUT`` seconds so orchestrators
    can retry instead of racing through an upgrade.
    """
    # Check the dialect at engine level before opening the lock connection:
    # applying AUTOCOMMIT isolation via execution_options may be rejected on
    # dialects other than PostgreSQL, and non-PG setups must skip locking
    # entirely rather than fail while trying to skip it.
    if connectable.dialect.name != "postgresql":
        return None

    lock_connection = connectable.connect().execution_options(isolation_level="AUTOCOMMIT")

    deadline = time.monotonic() + MIGRATION_LOCK_TIMEOUT_SECONDS
    waited = False
    try:
        while True:
            if _try_acquire_migration_advisory_lock(lock_connection):
                if waited:
                    logger.info("Migration advisory lock acquired")
                return lock_connection

            if not waited:
                waited = True
                logger.warning(
                    "Another replica is running migrations; waiting up to %ss "
                    "for the migration advisory lock",
                    MIGRATION_LOCK_TIMEOUT_SECONDS,
                )
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Timed out waiting for the migration advisory lock "
                    f"({MIGRATION_LOCK_TIMEOUT_SECONDS}s). Another upgrade may be "
                    "stuck; inspect pg_locks for the holder or raise "
                    "ALEMBIC_LOCK_TIMEOUT."
                )
            time.sleep(LOCK_POLL_INTERVAL_SECONDS)
    except BaseException:
        # Any failure while polling (e.g. the connection dropping mid-poll)
        # must not leak the dedicated lock connection; the timeout path raises
        # through here as well.
        lock_connection.close()
        raise


def _release_migration_advisory_lock(lock_connection):
    """Release the migration advisory lock if we hold one."""
    if lock_connection is None:
        return
    try:
        lock_connection.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": MIGRATION_ADVISORY_LOCK_KEY},
        )
    except Exception:
        # This runs in a ``finally`` after the migration itself: when the same
        # database problem failed the migration, the unlock fails too, and a
        # propagating unlock error would replace the original migration error.
        # Closing the connection releases the session-scoped lock anyway, so
        # the explicit unlock is belt-and-suspenders only.
        logger.warning("Failed to release migration advisory lock", exc_info=True)
    finally:
        lock_connection.close()


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

    Concurrent replicas are serialized with a Postgres advisory lock so only
    one process performs the upgrade while the rest wait and then find the
    database already at head.

    """
    url = get_database_settings().admin_url

    connectable = create_engine(url)

    lock_connection = _acquire_migration_advisory_lock(connectable)
    try:
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
    finally:
        _release_migration_advisory_lock(lock_connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
