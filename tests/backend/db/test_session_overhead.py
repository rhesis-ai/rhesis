"""How many statements a tenant-scoped session spends on bookkeeping.

``get_db_with_tenant_variables`` used to blank the RLS GUCs in its ``finally``
block. That reset was described as belt-and-suspenders "before connection
returns to pool", but the GUCs are set with ``is_local=true``, so the COMMIT the
context manager already does discards them; the reset only opened a fresh
transaction for ``close()`` to roll back. It cost two extra ``set_config`` round
trips on every request. Applying the scope also ran ``set_config`` twice. These
tests pin the cheaper shape so it cannot creep back.
"""

import pytest
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

from rhesis.backend.app.database import get_db_with_tenant_variables


class _StatementCounter:
    """Record every statement the engine sends while it is attached."""

    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[object] = []

    def __enter__(self) -> "_StatementCounter":
        event.listen(Engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc_info) -> None:
        event.remove(Engine, "before_cursor_execute", self._record)

    def _record(self, conn, cursor, statement, parameters, context, executemany) -> None:
        self.statements.append(" ".join(statement.split()))
        self.params.append(parameters)

    @property
    def set_config_calls(self) -> list[object]:
        return [p for s, p in zip(self.statements, self.params, strict=True) if "set_config" in s]


@pytest.mark.integration
class TestTenantSessionOverhead:
    def test_empty_session_spends_one_set_config_call(self, test_org_id):
        """Applying the scope begins the transaction, and ``after_begin`` sets the GUCs.

        It used to be two: the apply also ran ``set_config`` itself, right after the
        ``after_begin`` listener had run the same one on the transaction that apply
        opened. Four before the reset was removed.
        """
        with _StatementCounter() as counter:
            with get_db_with_tenant_variables(str(test_org_id), str(test_org_id)):
                pass

        assert len(counter.set_config_calls) == 1, counter.statements

    def test_scope_is_never_blanked_on_the_way_out(self, test_org_id):
        """No ``set_config`` runs with empty ids -- that was the reset's signature."""
        with _StatementCounter() as counter:
            with get_db_with_tenant_variables(str(test_org_id), str(test_org_id)):
                pass

        blanked = [p for p in counter.set_config_calls if not p.get("org_id")]
        assert blanked == [], f"the GUC reset is back: {blanked}"

    def test_rls_guc_is_still_set_for_queries_inside_the_block(self, test_org_id):
        """The point of the function still holds: work inside sees its tenant."""
        with get_db_with_tenant_variables(str(test_org_id), str(test_org_id)) as db:
            current = db.execute(
                text("SELECT current_setting('app.current_organization', true)")
            ).scalar()

        assert current == str(test_org_id)

    def test_guc_does_not_survive_into_the_next_session_on_the_same_connection(self, test_org_id):
        """What the reset was guarding against, checked directly.

        ``is_local=true`` means the value dies with the transaction, so a later
        session that happens to be handed the same pooled connection starts
        clean without anyone blanking it.
        """
        with get_db_with_tenant_variables(str(test_org_id), str(test_org_id)):
            pass

        with get_db_with_tenant_variables() as db:
            leaked = db.execute(
                text("SELECT current_setting('app.current_organization', true)")
            ).scalar()

        assert leaked in ("", None), f"tenant id leaked across sessions: {leaked!r}"

    def test_a_scope_change_inside_a_transaction_is_applied_at_once(self, test_org_id):
        """With a transaction already open, after_begin won't run again; apply sets it."""
        from rhesis.backend.app.database import bind_scope_to_session

        with get_db_with_tenant_variables() as db:
            db.execute(text("SELECT 1"))
            bind_scope_to_session(db, str(test_org_id), str(test_org_id))
            current = db.execute(
                text("SELECT current_setting('app.current_organization', true)")
            ).scalar()

        assert current == str(test_org_id)

    def test_entering_the_scope_a_session_already_has_costs_nothing(self, test_org_id):
        """A job binds its session's scope, then storage enters the same project scope."""
        from uuid import uuid4

        from rhesis.backend.app.database import bind_scope_to_session, temporary_project_scope

        project_id = str(uuid4())
        with get_db_with_tenant_variables() as db:
            bind_scope_to_session(db, str(test_org_id), "", project_id)
            with _StatementCounter() as counter:
                with temporary_project_scope(db, str(test_org_id), "", project_id):
                    current = db.execute(
                        text("SELECT current_setting('app.current_project', true)")
                    ).scalar()

        assert counter.set_config_calls == []
        assert current == project_id
