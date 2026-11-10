"""Let a table owner without BYPASSRLS run migrations on FORCE RLS tables.

Managed Postgres (RDS, Aurora, Cloud SQL, Azure) has no SUPERUSER, and on PG16
only a BYPASSRLS role can grant BYPASSRLS, so there the migration owner runs
without it. FORCE ROW LEVEL SECURITY then applies the tenant policies to the
owner too, and any migration touching rows outside an org scope (seed and
lookup data, or anything that runs before an org exists) fails with
``unrecognized configuration parameter "app.current_organization"``.

So while migrations run, FORCE is switched off on every table the owner can
alter, which makes the owner bypass RLS exactly as a BYPASSRLS role does. It
goes back on before every commit:

- ``begin``, and after any statement that sets FORCE: switch FORCE off on the
  owned tables that have it, remembering them by OID (so a rename doesn't lose
  one). Catching the statement matters: a new table's migration forces it and
  may seed it straight away.
- ``commit``: put FORCE back on every remembered table that still exists. This
  also runs for the commit ``autocommit_block()`` makes mid-migration.
- ``rollback``: nothing to put back, the ALTERs roll back with everything else.
- before a statement that drops FORCE: put FORCE back first, so the statement
  acts on the real state and the tables it un-forces stay that way. This works
  for dynamic SQL in a DO block too, since nothing parses table names.

Does nothing when the role is SUPERUSER or has BYPASSRLS, so our own
deployments migrate exactly as before.
"""

import logging
import re

from sqlalchemy import event, text
from sqlalchemy.engine import Connection

logger = logging.getLogger("alembic.runtime.migration")

# Member rather than owner: a member of the owning role may alter the table too.
_OWNED_FORCED = """
    SELECT c.oid, c.oid::regclass::text FROM pg_class c
    WHERE c.relkind IN ('r', 'p') AND c.relforcerowsecurity
      AND pg_has_role(current_user, c.relowner, 'MEMBER')
"""

_SETS_FORCE = re.compile(r"\bFORCE\s+ROW\s+LEVEL\s+SECURITY", re.IGNORECASE)
_DROPS_FORCE = re.compile(r"\bNO\s+FORCE\s+ROW\s+LEVEL\s+SECURITY", re.IGNORECASE)


def _owner_bypasses_rls(connection: Connection) -> bool:
    bypasses = connection.execute(
        text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    # End the transaction autobegun above, so Alembic starts its own.
    connection.rollback()
    return bool(bypasses)


class _ForceRlsSuspension:
    def __init__(self, connection: Connection):
        self._connection = connection
        self._owed: set[int] = set()

    def _cursor(self):
        # Straight to the driver: SQLAlchemy is mid-commit when restore runs, and
        # our own ALTERs must not reach the statement listeners below.
        return self._connection.connection.dbapi_connection.cursor()

    def _in_autocommit(self) -> bool:
        return bool(self._connection.connection.dbapi_connection.autocommit)

    def suspend(self, *_args, **_kwargs) -> None:
        # Inside autocommit_block() each ALTER would commit on its own.
        if self._in_autocommit():
            return
        with self._cursor() as cur:
            cur.execute(_OWNED_FORCED)
            for oid, name in cur.fetchall():
                cur.execute(f"ALTER TABLE {name} NO FORCE ROW LEVEL SECURITY")
                self._owed.add(oid)

    def restore(self, *_args, **_kwargs) -> None:
        if not self._owed:
            return
        with self._cursor() as cur:
            cur.execute(
                "SELECT oid::regclass::text FROM pg_class WHERE oid = ANY(%s)",
                (sorted(self._owed),),
            )
            for (name,) in cur.fetchall():
                cur.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        self._owed.clear()

    def forget(self, *_args) -> None:
        self._owed.clear()

    def before_statement(self, _conn, _cursor, statement, *_args) -> None:
        if _DROPS_FORCE.search(statement):
            self.restore()

    def after_statement(self, _conn, _cursor, statement, *_args) -> None:
        if _SETS_FORCE.search(statement):
            self.suspend()


def suspend_force_rls_for_owner(connection: Connection):
    """Install the suspension on *connection*; return Alembic's on_version_apply hook.

    The hook catches FORCE set in a way the statement text doesn't show (a
    function call, say). Returns None (and installs nothing) when the owner
    bypasses RLS anyway or the database isn't Postgres.
    """
    if connection.dialect.name != "postgresql" or _owner_bypasses_rls(connection):
        return None
    logger.info(
        "Migration role lacks BYPASSRLS: lifting FORCE ROW LEVEL SECURITY on its "
        "tables while migrating, restored before each commit"
    )
    suspension = _ForceRlsSuspension(connection)
    event.listen(connection, "begin", suspension.suspend)
    event.listen(connection, "commit", suspension.restore)
    event.listen(connection, "rollback", suspension.forget)
    event.listen(connection, "before_cursor_execute", suspension.before_statement)
    event.listen(connection, "after_cursor_execute", suspension.after_statement)
    return suspension.suspend
