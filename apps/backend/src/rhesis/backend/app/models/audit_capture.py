"""Change capture for the audit log.

Every write reaches the database through a session, so two session listeners
see all of them and emit one ``AuditRecorded`` per change with ``db=session``.
The audit sink writes it in the same transaction, so the entry commits or
rolls back with the change.

- ``after_flush`` covers unit-of-work writes (``add``, attribute changes,
  ``delete``). Not ``before_flush``: a new row's server-generated id only
  exists once its INSERT has run, and attribute history is still intact here.
- ``do_orm_execute`` covers statements: ``crud_utils.bulk_update`` and
  ``bulk_delete``, ORM inserts, and Core writes to link tables. It adds the
  columns it needs to the statement's RETURNING, so it learns exactly which
  rows changed.

Nothing is captured unless ``FeatureName.AUDIT_LOG`` is registered (the EE
audit package does that with its sink), the session has a provenance (a
request or a job), and the org is entitled. A write with neither request nor
job (a migration, a script) has no actor to name and is not recorded.

Inside a job, creates are summarized: one row per resource type per
transaction, written just before commit (``ChangeSummary``). Updates and
deletes stay one row per object.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property
from typing import Any, Optional
from uuid import UUID

from pydantic_core import to_jsonable_python
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from rhesis.backend.app.models.audit_policy import AuditLink, AuditPolicy

logger = logging.getLogger(__name__)

# Identity and timestamps every row carries; never a change.
_BOOKKEEPING = frozenset({"id", "nano_id", "created_at", "updated_at"})
_LABEL_COLUMNS = ("name", "title", "email", "filename")
# Above this, a job summary keeps only the count.
SUMMARY_ID_LIMIT = 10_000
_RETURNING_PREFIX = "_audit_"

_ENTITLED_KEY = "_audit_entitled"
_ACTOR_LABELS_KEY = "_audit_actor_labels"
_JOB_CREATES_KEY = "_audit_job_creates"

_listeners_registered = False


class AuditCaptureError(RuntimeError):
    """A write the audit log cannot account for."""


# ---------------------------------------------------------------------------
# Per-table plans, built once from the declarations
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Field:
    name: str  # column name, as recorded
    key: str  # mapped attribute key
    kind: str  # value | secret | content


@dataclass(frozen=True)
class _Plan:
    resource: str
    fields: tuple[_Field, ...]
    org_column: str
    label: Optional[str]
    has_project: bool
    # (relationship key, link, the link column that points at this model)
    link_relationships: tuple[tuple[str, AuditLink, str], ...]


@dataclass(frozen=True)
class _Plans:
    by_table: dict[str, Any]  # _Plan or AuditLink
    resource_by_class: dict[str, str]
    class_by_resource: dict[str, type]
    mapper_count: int


_plans_cache: Optional[_Plans] = None


def _field_kind(column, policy: AuditPolicy) -> str:
    from rhesis.backend.app.utils.encryption import EncryptedString

    if isinstance(column.type, EncryptedString) or column.name in policy.secret:
        return "secret"
    return "content" if column.name in policy.content else "value"


def _link_relationships(mapper) -> tuple:
    found = []
    for rel in mapper.relationships:
        link = rel.secondary.info.get("audit") if rel.secondary is not None else None
        if isinstance(link, AuditLink) and not rel.viewonly:
            found.append((rel.key, link, rel.synchronize_pairs[0][1].name))
    return tuple(found)


def _plan_for(mapper, policy: AuditPolicy) -> _Plan:
    table = mapper.local_table
    skipped = _BOOKKEEPING | {policy.org_column} | set(policy.ignore)
    fields = tuple(
        _Field(prop.columns[0].name, prop.key, _field_kind(prop.columns[0], policy))
        for prop in mapper.column_attrs
        if prop.columns[0].table is table and prop.columns[0].name not in skipped
    )
    label = policy.label or next((c for c in _LABEL_COLUMNS if c in table.c), None)
    return _Plan(
        resource=policy.resource or table.name,
        fields=fields,
        org_column=policy.org_column,
        label=label,
        has_project="project_id" in table.c,
        link_relationships=_link_relationships(mapper),
    )


def audit_policy_of(cls) -> Any:
    """A mapped class's declaration: an ``AuditPolicy`` or an ``AuditLink``."""
    return getattr(cls, "__audit__", None) or AuditPolicy()


def plans() -> _Plans:
    """Plans for every audited table, rebuilt when more models get mapped (EE)."""
    global _plans_cache
    from rhesis.backend.app.models.base import Base

    mappers = list(Base.registry.mappers)
    if _plans_cache is not None and _plans_cache.mapper_count == len(mappers):
        return _plans_cache

    by_table: dict[str, Any] = {}
    resource_by_class: dict[str, str] = {}
    class_by_resource: dict[str, type] = {}
    for mapper in mappers:
        policy = audit_policy_of(mapper.class_)
        if isinstance(policy, AuditLink):
            by_table[mapper.local_table.name] = policy
        elif policy.audited:
            plan = _plan_for(mapper, policy)
            by_table[mapper.local_table.name] = plan
            resource_by_class[mapper.class_.__name__] = plan.resource
            class_by_resource.setdefault(plan.resource, mapper.class_)
    for table in Base.metadata.tables.values():
        if isinstance(table.info.get("audit"), AuditLink):
            by_table[table.name] = table.info["audit"]

    _plans_cache = _Plans(by_table, resource_by_class, class_by_resource, len(mappers))
    return _plans_cache


# ---------------------------------------------------------------------------
# Who, and whether this org records
# ---------------------------------------------------------------------------


def audit_registered() -> bool:
    """Whether the audit log is installed at all (the EE package registers it)."""
    from rhesis.backend.app.features import FeatureName, FeatureRegistry

    return FeatureRegistry.is_registered(FeatureName.AUDIT_LOG)


def audit_enabled(session: Session, organization_id) -> bool:
    """Whether ``organization_id`` records audit events. Cached per session."""
    from rhesis.backend.app.features import FeatureName, FeatureRegistry
    from rhesis.backend.app.models.organization import Organization

    if organization_id is None or not audit_registered():
        return False
    cache = session.info.setdefault(_ENTITLED_KEY, {})
    key = str(organization_id)
    if key not in cache:
        with session.no_autoflush:
            org = session.get(Organization, UUID(key))
        cache[key] = FeatureRegistry.is_available(FeatureName.AUDIT_LOG, org)
    return cache[key]


def session_org(session: Session) -> Optional[str]:
    """The org the session's RLS settings name, if any."""
    scope = session.info.get("_scope")
    if scope is not None and scope.organization_id:
        return str(scope.organization_id)
    tenant_vars = session.info.get("_tenant_vars") or {}
    return tenant_vars.get("org_id") or None


@dataclass
class _Context:
    session: Session
    provenance: Any  # RequestProvenance

    @cached_property
    def occurred_at(self) -> datetime:
        return datetime.now(timezone.utc)

    @cached_property
    def ids(self) -> tuple[str, str]:
        from rhesis.backend.events.correlation import resolve_ids

        return resolve_ids()

    @cached_property
    def actor_label(self) -> Optional[str]:
        return session_user_label(self.session, self.provenance.actor_id)


def user_label(name: Optional[str], email: Optional[str]) -> Optional[str]:
    """How an actor is named in the log: ``Name <email>``, or the email alone."""
    return f"{name} <{email}>" if name else email


def session_user_label(session: Session, user_id: Optional[str]) -> Optional[str]:
    """``user_label`` for ``user_id``, looked up once per session."""
    from rhesis.backend.app.models.user import User

    if not user_id:
        return None
    labels = session.info.setdefault(_ACTOR_LABELS_KEY, {})
    if user_id not in labels:
        row = (
            session.connection()
            .execute(select(User.name, User.email).where(User.id == UUID(user_id)))
            .first()
        )
        labels[user_id] = user_label(row.name, row.email) if row is not None else None
    return labels[user_id]


def _context(session: Session) -> Optional[_Context]:
    from rhesis.backend.app.provenance import provenance_of

    if not audit_registered():
        return None
    provenance = provenance_of(session)
    return _Context(session, provenance) if provenance is not None else None


# ---------------------------------------------------------------------------
# Turning changes into events
# ---------------------------------------------------------------------------


def _json(value: Any) -> Any:
    try:
        return to_jsonable_python(value)
    except Exception:
        return str(value)


def _field_changes(plan: _Plan, diffs: dict) -> tuple:
    from rhesis.backend.events.types import FieldChange

    changes = []
    for field in plan.fields:
        if field.name not in diffs:
            continue
        if field.kind == "secret":
            changes.append(FieldChange(field=field.name, kind="secret"))
            continue
        before, after = diffs[field.name]
        changes.append(
            FieldChange(field=field.name, kind=field.kind, before=_json(before), after=_json(after))
        )
    return tuple(changes)


def _verb(op: str, diffs: dict) -> str:
    """A soft delete is a delete, whatever else changed with it."""
    if op == "update" and "deleted_at" in diffs:
        before, after = diffs["deleted_at"]
        if before is None and after is not None:
            return "delete"
    return op


class _Recorder:
    """Collects one flush's or one statement's changes, then emits them."""

    def __init__(self, ctx: _Context):
        self.ctx = ctx
        self.events: list = []
        self.links: dict[tuple, dict] = {}

    def _org(self, org) -> Optional[str]:
        org = str(org) if org else session_org(self.ctx.session)
        return org if audit_enabled(self.ctx.session, org) else None

    def change(self, plan: _Plan, op: str, resource_id, org, project, label, diffs: dict) -> None:
        from rhesis.backend.app.provenance import Channel

        org = self._org(org)
        if org is None or resource_id is None:
            return
        verb = _verb(op, diffs)
        if verb == "create" and self.ctx.provenance.channel == Channel.JOB:
            _buffer_job_create(self.ctx.session, plan.resource, org, project, resource_id)
            return
        changes = () if verb == "delete" else _field_changes(plan, diffs)
        if verb == "update" and not changes:
            return
        self.events.append(
            self.event(
                plan.resource,
                verb,
                org,
                project,
                resource_id=resource_id,
                label=label,
                changes=changes,
            )
        )

    def link(self, link: AuditLink, row: dict, added: bool) -> None:
        owner = link.owner or plans().resource_by_class.get(row.get(link.owner_type))
        org = self._org(row.get("organization_id"))
        if owner is None or org is None:
            return
        key = (owner, str(row[link.owner_id]), link.field, org, row.get("project_id"))
        entry = self.links.setdefault(key, {"added": set(), "removed": set()})
        entry["added" if added else "removed"].add(str(row[link.linked_id]))

    def event(self, resource, verb, org, project, **fields):
        from rhesis.backend.events.audit_actions import audit_action
        from rhesis.backend.events.types import AuditRecorded

        provenance = self.ctx.provenance
        trace_id, span_id = self.ctx.ids
        return AuditRecorded(
            occurred_at=self.ctx.occurred_at,
            organization_id=org,
            project_id=project,
            user_id=provenance.actor_id,
            trace_id=trace_id,
            span_id=span_id,
            job_id=provenance.job_id,
            entity_type=resource,
            entity_id=fields.pop("resource_id", None),
            resource_label=fields.pop("label", None),
            source="audit",
            action=audit_action(f"{resource}:{verb}"),
            outcome="success",
            actor_type=provenance.actor_type,
            actor_credential_id=provenance.credential_id,
            actor_credential_hint=provenance.credential_hint,
            actor_label=self.ctx.actor_label,
            channel=provenance.channel,
            ip=provenance.ip,
            user_agent=provenance.user_agent,
            request_id=provenance.request_id,
            **fields,
        )

    def _link_events(self) -> list:
        from rhesis.backend.events.types import FieldChange

        out = []
        for (owner, owner_id, field, org, project), ids in self.links.items():
            added, removed = (
                sorted(ids["added"] - ids["removed"]),
                sorted(ids["removed"] - ids["added"]),
            )
            if not added and not removed:
                continue
            change = FieldChange(
                field=field, kind="value", before=removed or None, after=added or None
            )
            out.append(
                self.event(
                    owner,
                    "update",
                    org,
                    project,
                    resource_id=owner_id,
                    label=_loaded_label(self.ctx.session, owner, owner_id),
                    changes=(change,),
                )
            )
        return out

    def emit(self) -> None:
        from rhesis.backend.events.dispatcher import emit

        for audit_event in self.events + self._link_events():
            emit(audit_event, db=self.ctx.session)


def _loaded_label(session: Session, resource: str, resource_id: str) -> Optional[str]:
    """The owner's name, when the session already holds it. Never queries."""
    cls = plans().class_by_resource.get(resource)
    plan = plans().by_table.get(cls.__table__.name) if cls is not None else None
    if plan is None or plan.label is None:
        return None
    obj = session.identity_map.get(inspect(cls).identity_key_from_primary_key((UUID(resource_id),)))
    return inspect(obj).dict.get(plan.label) if obj is not None else None


# ---------------------------------------------------------------------------
# Job summaries
# ---------------------------------------------------------------------------


def _buffer_job_create(session: Session, resource, org, project, resource_id) -> None:
    buffer = session.info.setdefault(_JOB_CREATES_KEY, {})
    buffer.setdefault((resource, org, str(project) if project else None), []).append(resource_id)


def _write_job_summaries(session: Session) -> None:
    from rhesis.backend.events.types import ChangeSummary

    if not audit_registered() or not session.info.get(_JOB_CREATES_KEY):
        return
    # Creates still pending would otherwise flush after this hook.
    session.flush()
    buffer = session.info.pop(_JOB_CREATES_KEY, None) or {}
    ctx = _context(session)
    if ctx is None:
        return
    recorder = _Recorder(ctx)
    for (resource, org, project), ids in buffer.items():
        summary = ChangeSummary(
            count=len(ids), ids=tuple(ids) if len(ids) <= SUMMARY_ID_LIMIT else ()
        )
        recorder.events.append(recorder.event(resource, "create", org, project, summary=summary))
    recorder.emit()


# ---------------------------------------------------------------------------
# Unit-of-work writes
# ---------------------------------------------------------------------------


def _object_diffs(plan: _Plan, state, op: str) -> dict:
    diffs = {}
    for field in plan.fields:
        if op == "create":
            value = state.dict.get(field.key)
            if value is not None:
                diffs[field.name] = (None, value)
        elif op == "update":
            history = state.attrs[field.key].history
            if not history.has_changes():
                continue
            before = history.deleted[0] if history.deleted else None
            after = history.added[0] if history.added else None
            if before != after:
                diffs[field.name] = (before, after)
    return diffs


def _object_org(plan: _Plan, state):
    org = state.dict.get(plan.org_column)
    if org is None and plan.org_column in state.attrs:
        deleted = state.attrs[plan.org_column].history.deleted
        org = deleted[0] if deleted else None
    return org


def _capture_relationship_links(recorder: _Recorder, plan: _Plan, state) -> None:
    """Link rows the ORM writes for a changed collection, e.g. ``test_set.metrics``."""
    for key, link, own_column in plan.link_relationships:
        history = state.attrs[key].history
        own_id = state.dict.get("id")
        for added, others in ((True, history.added), (False, history.deleted)):
            for other in others:
                other_id = inspect(other).dict.get("id")
                is_owner = own_column == link.owner_id
                row = {
                    link.owner_id: own_id if is_owner else other_id,
                    link.linked_id: other_id if is_owner else own_id,
                    "organization_id": _object_org(plan, state),
                }
                recorder.link(link, row, added)


def _capture_object(recorder: _Recorder, obj, op: str) -> None:
    state = inspect(obj)
    plan = plans().by_table.get(state.mapper.local_table.name)
    if plan is None:
        return
    if isinstance(plan, AuditLink):
        if op != "update":
            recorder.link(plan, {**state.dict}, added=op == "create")
        return
    if op != "delete":
        _capture_relationship_links(recorder, plan, state)
    recorder.change(
        plan,
        op,
        resource_id=state.dict.get("id"),
        org=_object_org(plan, state),
        project=state.dict.get("project_id") if plan.has_project else None,
        label=state.dict.get(plan.label) if plan.label else None,
        diffs=_object_diffs(plan, state, op),
    )


def _after_flush(session: Session, flush_context) -> None:
    ctx = _context(session)
    if ctx is None:
        return
    recorder = _Recorder(ctx)
    for op, objects in (
        ("create", session.new),
        ("update", session.dirty),
        ("delete", session.deleted),
    ):
        for obj in list(objects):
            _capture_object(recorder, obj, op)
    recorder.emit()


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


def _returned(name: str) -> str:
    return f"{_RETURNING_PREFIX}{name}"


def _updated_columns(plan: _Plan, statement) -> set[str]:
    values = getattr(statement, "_values", None)
    if values is None:
        values = dict(getattr(statement, "_ordered_values", None) or ())
    if not values:
        raise AuditCaptureError(
            f"cannot tell which columns a bulk UPDATE of {plan.resource} sets; "
            "use crud_utils.bulk_update"
        )
    keys = {k if isinstance(k, str) else getattr(k, "key", None) for k in values}
    keys |= {getattr(k, "name", None) for k in values if not isinstance(k, str)}
    return {f.name for f in plan.fields if f.name in keys or f.key in keys}


def _returning_columns(plan, table, op: str, statement) -> list[str]:
    if isinstance(plan, AuditLink):
        names = [plan.owner_id, plan.linked_id, plan.owner_type, "organization_id", "project_id"]
    else:
        names = ["id", plan.org_column, plan.label, "project_id" if plan.has_project else None]
        if op == "create":
            names += [f.name for f in plan.fields]
        elif op == "update":
            names += sorted(_updated_columns(plan, statement))
    return [n for n in dict.fromkeys(names) if n and n in table.c]


def _statement_rows(recorder: _Recorder, plan, op: str, rows: list[dict]) -> None:
    for row in rows:
        if isinstance(plan, AuditLink):
            if op != "update":
                recorder.link(plan, row, added=op == "create")
            continue
        diffs = {f.name: (None, row[f.name]) for f in plan.fields if f.name in row}
        recorder.change(
            plan,
            op,
            resource_id=row.get("id"),
            org=row.get(plan.org_column),
            project=row.get("project_id"),
            label=row.get(plan.label) if plan.label else None,
            diffs=diffs,
        )


def _on_execute(orm_execute_state):
    if not orm_execute_state.statement.is_dml:
        return None
    statement = orm_execute_state.statement
    table = getattr(statement, "table", None)
    plan = plans().by_table.get(getattr(table, "name", None))
    if plan is None:
        return None
    session = orm_execute_state.session
    ctx = _context(session)
    scope_org = session_org(session)
    if ctx is None or (scope_org and not audit_enabled(session, scope_org)):
        return None

    op = (
        "create"
        if orm_execute_state.is_insert
        else "update"
        if orm_execute_state.is_update
        else "delete"
    )
    names = _returning_columns(plan, table, op, statement)
    statement = statement.returning(*(table.c[n].label(_returned(n)) for n in names))
    frozen = orm_execute_state.invoke_statement(statement=statement).freeze()

    prefix = len(_RETURNING_PREFIX)
    rows = [
        {k[prefix:]: v for k, v in row.items() if k.startswith(_RETURNING_PREFIX)}
        for row in frozen().mappings()
    ]
    recorder = _Recorder(ctx)
    _statement_rows(recorder, plan, op, rows)
    recorder.emit()
    return frozen()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _before_commit(session: Session) -> None:
    if not session.in_nested_transaction():
        _write_job_summaries(session)


def _after_transaction_end(session: Session, transaction) -> None:
    if transaction.parent is None:
        session.info.pop(_JOB_CREATES_KEY, None)


def setup_audit_listeners() -> None:
    """Register the capture listeners. Called once from ``models/__init__.py``,
    after the scope listeners, so statements already carry the tenant filter."""
    global _listeners_registered
    if _listeners_registered:
        return
    event.listen(Session, "after_flush", _after_flush)
    event.listen(Session, "do_orm_execute", _on_execute)
    event.listen(Session, "before_commit", _before_commit)
    event.listen(Session, "after_transaction_end", _after_transaction_end)
    _listeners_registered = True
