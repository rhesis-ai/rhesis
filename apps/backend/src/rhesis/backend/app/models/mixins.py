import functools
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, ForeignKey, and_, event
from sqlalchemy.orm import Session, declared_attr, object_session, relationship
from sqlalchemy.orm.exc import DetachedInstanceError

from .guid import GUID

logger = logging.getLogger(__name__)


def safe_relationship(default_factory=list):
    """Decorator for properties that access relationship attributes.

    After delete_item() commits, the RLS session variable
    (app.current_organization) may no longer be set on the DB connection.
    Any lazy-load of a relationship during response serialization would
    then fail with DetachedInstanceError. This decorator catches that
    case and returns a safe default so the response can still be
    serialized.
    """

    def decorator(method):
        @functools.wraps(method)
        def wrapper(self):
            try:
                return method(self)
            except DetachedInstanceError as exc:
                logger.warning(
                    "Suppressed lazy-load error on %s.%s: %s",
                    type(self).__name__,
                    method.__name__,
                    exc,
                )
                return default_factory()

        return wrapper

    return decorator


class TagsMixin:
    @declared_attr
    def _tags_relationship(cls):
        from .tag import TaggedItem

        return relationship(
            "TaggedItem",
            primaryjoin=lambda: and_(
                TaggedItem.entity_id == cls.id, TaggedItem.entity_type == cls.__name__
            ),
            foreign_keys=[TaggedItem.entity_id, TaggedItem.entity_type],
            overlaps="_tags_relationship",
            cascade="all, delete-orphan",
        )

    @property
    @safe_relationship(default_factory=list)
    def tags(self):
        # Deduplicate tags by ID to handle duplicate TaggedItem records
        seen_tag_ids = set()
        unique_tags = []
        for tagged_item in self._tags_relationship:
            if tagged_item.tag and tagged_item.tag.id not in seen_tag_ids:
                seen_tag_ids.add(tagged_item.tag.id)
                unique_tags.append(tagged_item.tag)
        return unique_tags

    @tags.setter
    def tags(self, tag_objects):
        if tag_objects is None:
            tag_objects = []
        self._tags_relationship.clear()
        for tag in tag_objects:
            from .tag import TaggedItem

            # Handle both tag objects and tag names/IDs
            if isinstance(tag, str):
                # If it's a string, assume it's a tag name and create a new tag
                from .tag import Tag

                tag_obj = Tag(name=tag)
            else:
                tag_obj = tag

            tagged_item = TaggedItem(
                tag=tag_obj, entity_id=self.id, entity_type=self.__class__.__name__
            )
            self._tags_relationship.append(tagged_item)


class CommentsMixin:
    """Mixin that provides polymorphic comment relationships"""

    @declared_attr
    def comments(cls):
        """Polymorphic comment relationship"""
        return relationship(
            "Comment",
            primaryjoin=(
                f"and_({cls.__name__}.id == foreign(Comment.entity_id), "
                f"Comment.entity_type == '{cls.__name__}', "
                f"Comment.deleted_at.is_(None))"
            ),
            viewonly=True,
            uselist=True,
        )


class FilesMixin:
    """Mixin that provides polymorphic file relationships"""

    @declared_attr
    def files(cls):
        """Polymorphic file relationship"""
        return relationship(
            "File",
            primaryjoin=(
                f"and_({cls.__name__}.id == foreign(File.entity_id), "
                f"File.entity_type == '{cls.__name__}', "
                f"File.deleted_at.is_(None))"
            ),
            viewonly=True,
            uselist=True,
        )


class TasksMixin:
    """Mixin that provides polymorphic task relationships"""

    @declared_attr
    def tasks(cls):
        """Polymorphic task relationship"""
        return relationship(
            "Task",
            primaryjoin=(
                f"and_({cls.__name__}.id == foreign(Task.entity_id), "
                f"Task.entity_type == '{cls.__name__}', "
                f"Task.deleted_at.is_(None))"
            ),
            viewonly=True,
            uselist=True,
        )


class CountsMixin:
    """Mixin that provides count properties for comments and tasks"""

    @property
    @safe_relationship(default_factory=int)
    def comments_count(self):
        """Get the count of comments for this entity"""
        return len(self.comments) if hasattr(self, "comments") and self.comments else 0

    @property
    @safe_relationship(default_factory=int)
    def tasks_count(self):
        """Get the count of tasks for this entity"""
        return len(self.tasks) if hasattr(self, "tasks") and self.tasks else 0

    @property
    @safe_relationship(default_factory=int)
    def files_count(self):
        """Get the count of files for this entity"""
        return len(self.files) if hasattr(self, "files") and self.files else 0

    @property
    @safe_relationship(default_factory=dict)
    def counts(self):
        """Get the counts of comments, tasks, and files for this entity"""
        counts = {}

        # Add comment count if the model has comments relationship
        if hasattr(self, "comments"):
            counts["comments"] = self.comments_count

        # Add task count if the model has tasks relationship
        if hasattr(self, "tasks"):
            counts["tasks"] = self.tasks_count

        # Add file count if the model has files relationship
        if hasattr(self, "files"):
            counts["files"] = self.files_count

        return counts


class OrganizationMixin:
    """Mixin for organization-level multi-tenancy"""

    organization_id = Column(GUID(), ForeignKey("organization.id"), nullable=True, index=True)

    @declared_attr
    def organization(cls):
        return relationship("Organization", foreign_keys=[cls.organization_id])


class UserOwnedMixin:
    """Mixin for user ownership"""

    user_id = Column(GUID(), ForeignKey("user.id"), nullable=True)

    @declared_attr
    def user(cls):
        return relationship("User", foreign_keys=[cls.user_id])


class ActivityTrackableMixin:
    """
    Mixin to mark entities that should appear in recent activities.

    Entities with this mixin will automatically be included in the
    /services/recent-activities endpoint.

    No additional fields or methods required - this is a marker mixin.
    """

    pass


# For entities that need both
class OrganizationAndUserMixin(OrganizationMixin, UserOwnedMixin):
    """Mixin for both organization and user ownership"""

    pass


class ProjectMixin:
    """Mixin for project-level multi-tenancy.

    Adds a nullable project_id FK so entities can be scoped to a project.
    NULL means the entity is org-wide and visible in every project's view
    (the auto-filter listener applies ``project_id = :pid OR project_id IS NULL``).
    """

    project_id = Column(GUID(), ForeignKey("project.id"), nullable=True, index=True)

    @declared_attr
    def project(cls):
        return relationship("Project", foreign_keys=[cls.project_id])


def _annotation_entry(annotation) -> dict:
    """The shape the frontend reads for one annotation embedded in a parent payload."""
    status = annotation.status
    user = annotation.user
    return {
        "annotation_id": str(annotation.id),
        "target_type": annotation.target_type,
        "reference": annotation.target_reference,
        "status": {"status_id": str(status.id), "name": status.name} if status else None,
        "user": {
            "id": str(user.id),
            "given_name": user.given_name,
            "family_name": user.family_name,
        }
        if user
        else None,
        "comments": annotation.comments,
        "updated_at": _annotation_timestamp(annotation).isoformat(),
    }


def _annotation_timestamp(annotation) -> datetime:
    return (
        annotation.updated_at or annotation.created_at or datetime.min.replace(tzinfo=timezone.utc)
    )


def _annotation_sort_key(annotation) -> tuple:
    # Id breaks ties so rows written in the same transaction, which share a
    # timestamp, still resolve to one stable "latest".
    return _annotation_timestamp(annotation), str(annotation.id)


class AnnotationsMixin:
    """Human-annotation state of an entity, derived from its ``annotation`` rows.

    Subclasses set ``_annotations_entity_type`` to their entity-level target type
    (e.g. ``"test_result"``); the polymorphic relationship is matched on the class
    name, which is also the ``entity_type`` value stored on the annotation.
    """

    _annotations_entity_type: str = ""

    @declared_attr
    def annotations(cls):
        return relationship(
            "Annotation",
            primaryjoin=(
                f"and_({cls.__name__}.id == foreign(Annotation.entity_id), "
                f"Annotation.entity_type == '{cls.__name__}', "
                f"Annotation.deleted_at.is_(None))"
            ),
            viewonly=True,
            uselist=True,
        )

    def _compute_annotation_state(self):
        """Returns (last_annotation, matches_annotation, annotation_summary).

        Cached on the instance: the three properties below each call this and
        response serialization reads all three back-to-back for the same row.
        """
        cached = self.__dict__.get("_annotation_state_cache")
        if cached is None:
            cached = self._compute_annotation_state_uncached()
            self.__dict__["_annotation_state_cache"] = cached
        return cached

    def _compute_annotation_state_uncached(self):
        rows = self.annotations
        if not rows:
            return None, False, None

        # Newest annotation per target, plus the newest entity-level one overall.
        summary: dict = {}
        latest = None
        for annotation in sorted(rows, key=_annotation_sort_key):
            reference = annotation.target_reference
            key = f"{annotation.target_type}:{reference}" if reference else annotation.target_type
            summary[key] = _annotation_entry(annotation)
            if annotation.target_type == self._annotations_entity_type:
                latest = annotation

        last = _annotation_entry(latest) if latest else None
        return last, self._matches(latest), summary

    def _matches(self, latest) -> bool:
        """Whether the entity-level verdict agrees with the automated one.

        Compared against ``original_status_id``, the snapshot taken before the
        first annotation overwrote the live status -- comparing against the live
        one would always agree and hide every genuine disagreement.
        """
        if latest is None or latest.status is None:
            return False
        automated = getattr(self, "original_status_id", None) or self._get_status_id_for_match()
        return bool(automated) and str(automated) == str(latest.status_id)

    def _get_status_id_for_match(self):
        """The automated status to fall back on when no snapshot was taken."""
        return getattr(self, "status_id", None)

    @property
    def last_annotation(self):
        return self._compute_annotation_state()[0]

    @property
    def matches_annotation(self):
        return self._compute_annotation_state()[1]

    @property
    def annotation_summary(self):
        return self._compute_annotation_state()[2]


class EmbeddableMixin:
    """
    Mixin for entities that support vector embeddings and full-text search.

    Entities with this mixin must implement to_searchable_text() which defines
    what text should be:
    1. Indexed for full-text search (via Embedding.searchable_text -> tsv column)
    2. Used as source for generating vector embeddings

    The searchable text is always captured at insert/update time (while the
    SQLAlchemy instance is still in memory) and passed directly to the embedding
    worker. No DB reload is performed after commit, which avoids RLS visibility
    and transaction snapshot race conditions.
    """

    @declared_attr
    def embeddings(cls):
        """Polymorphic embedding relationship"""
        return relationship(
            "Embedding",
            primaryjoin=(
                # foreign() wraps entity_id, the referencing side, not the parent id. Works anyways
                f"and_(Embedding.entity_id == foreign({cls.__name__}.id), "
                f"Embedding.entity_type == '{cls.__name__}')"
            ),
            # this likely overrides the foreign() above
            foreign_keys="[Embedding.entity_id]",
            viewonly=True,
            uselist=True,
        )

    def to_searchable_text(self) -> str:
        """
        Generate searchable text representation for this entity.

        Must be implemented by subclasses.

        Returns:
            str: Searchable text representation

        Example:
            >>> chunk.to_searchable_text()
            "While this document focuses on the evolving trends in AI safety research, ..."
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement to_searchable_text() method"
        )


# Defer embedding work to after commit so we never flush from inside flush (mapper events
# run during Session.flush, while EmbeddingGenerator may call get_or_create_status → flush).
_PENDING_EMBEDDING_JOBS_KEY = "pending_embedding_jobs"


def _queue_embedding_after_commit(target) -> None:
    """
    Queue an embedding job to run after the current transaction commits.

    The searchable text is always captured here, while the SQLAlchemy instance
    is still in memory. If to_searchable_text() fails, the job is not enqueued
    at all — we fail loudly rather than falling back to a DB reload after commit.
    """
    session = object_session(target)
    if session is None:
        logger.debug(
            "Deferred embedding: skip queue (no session) for %s",
            getattr(target, "id", None),
        )
        return

    if target.organization_id is None or target.user_id is None:
        logger.warning(
            "Skipping embedding for %s %s: organization_id or user_id is None",
            target.__class__.__name__,
            target.id,
        )
        return

    if not hasattr(target, "to_searchable_text"):
        logger.warning(
            "Skipping embedding for %s %s: to_searchable_text() not implemented",
            target.__class__.__name__,
            target.id,
        )
        return

    try:
        searchable_text = target.to_searchable_text()
    except Exception as exc:
        logger.error(
            "Skipping embedding for %s id=%s: to_searchable_text() failed at queue time: %s",
            target.__class__.__name__,
            target.id,
            exc,
        )
        return

    if not (searchable_text or "").strip():
        logger.info(
            "Deferred embedding: skipping queue for %s id=%s (empty searchable text)",
            target.__class__.__name__,
            getattr(target, "id", None),
        )
        return

    job: dict[str, Any] = {
        "entity_type": target.__class__.__name__,
        "entity_id": str(target.id),
        "user_id": str(target.user_id),
        "organization_id": str(target.organization_id),
        "project_id": str(target.project_id) if getattr(target, "project_id", None) else None,
        "searchable_text": searchable_text,
    }

    pending = session.info.setdefault(_PENDING_EMBEDDING_JOBS_KEY, [])
    pending.append(job)

    nested_tx = (
        session.in_nested_transaction() if hasattr(session, "in_nested_transaction") else False
    )
    logger.debug(
        "Deferred embedding: queued after_commit job for %s id=%s org=%s user=%s project=%s "
        "(session id=%s, pending_count=%s, in_transaction=%s, nested=%s)",
        job["entity_type"],
        job["entity_id"],
        job["organization_id"],
        job["user_id"],
        job["project_id"],
        id(session),
        len(pending),
        session.in_transaction(),
        nested_tx,
    )


@event.listens_for(Session, "after_commit")
def _process_pending_embedding_jobs(session: Session) -> None:
    jobs = session.info.pop(_PENDING_EMBEDDING_JOBS_KEY, None)
    if not jobs:
        return

    logger.info(
        "Deferred embedding: after_commit running %d job(s) (committed session id=%s)",
        len(jobs),
        id(session),
    )

    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.services.embedding.services import EmbeddingService

    for job in jobs:
        try:
            with get_db_with_tenant_variables(
                job["organization_id"],
                job["user_id"],
                job.get("project_id") or "",
            ) as db:
                embedding_service = EmbeddingService(db)
                embedding_service.enqueue_embedding(
                    entity_type=job["entity_type"],
                    entity_id=job["entity_id"],
                    searchable_text=job["searchable_text"],
                    user_id=job["user_id"],
                    organization_id=job["organization_id"],
                )
                logger.info(
                    "Deferred embedding: enqueue_embedding submitted for %s id=%s",
                    job["entity_type"],
                    job["entity_id"],
                )
        except Exception as e:
            logger.error(
                "Error running deferred embedding for %s %s: %s",
                job.get("entity_type"),
                job.get("entity_id"),
                e,
            )


# Event listeners for embedding generation
@event.listens_for(EmbeddableMixin, "after_insert", propagate=True)
def on_entity_insert(mapper, connection, target):
    if getattr(target, "user_id", None) is None:
        # Expected for telemetry traces and other service-generated rows that
        # carry no user context; downgraded from WARNING to avoid log noise.
        logger.debug(
            "Skipping embedding for %s %s: user_id is None",
            target.__class__.__name__,
            target.id,
        )
        return

    logger.debug(
        "Deferred embedding: after_insert hook for %s id=%s",
        target.__class__.__name__,
        getattr(target, "id", None),
    )
    try:
        _queue_embedding_after_commit(target)
    except Exception as e:
        logger.error(
            "Error enqueuing embedding for %s %s: %s",
            target.__class__.__name__,
            target.id,
            e,
        )


@event.listens_for(EmbeddableMixin, "after_update", propagate=True)
def on_entity_update(mapper, connection, target):
    if getattr(target, "user_id", None) is None:
        logger.debug(
            "Skipping embedding for %s %s: user_id is None",
            target.__class__.__name__,
            target.id,
        )
        return

    logger.debug(
        "Deferred embedding: after_update hook for %s id=%s",
        target.__class__.__name__,
        getattr(target, "id", None),
    )
    try:
        _queue_embedding_after_commit(target)
    except Exception as e:
        logger.error(
            "Error enqueuing embedding for %s %s: %s",
            target.__class__.__name__,
            target.id,
            e,
        )


@event.listens_for(Session, "after_soft_rollback")
def _clear_pending_embedding_jobs(session: Session, transaction) -> None:
    pending = session.info.get(_PENDING_EMBEDDING_JOBS_KEY)
    if pending:
        logger.info(
            "Deferred embedding: dropped %d pending job(s) on soft rollback (session id=%s)",
            len(pending),
            id(session),
        )
    session.info.pop(_PENDING_EMBEDDING_JOBS_KEY, None)
