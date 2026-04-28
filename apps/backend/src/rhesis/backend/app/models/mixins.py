import functools
import hashlib
import logging

from sqlalchemy import Column, Connection, ForeignKey, and_, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, declared_attr, object_session, relationship
from sqlalchemy.orm.exc import DetachedInstanceError

from .guid import GUID

logger = logging.getLogger(__name__)


def safe_relationship(default_factory=list):
    """Decorator for properties that access relationship attributes.

    After delete_item() commits, the RLS session variable
    (app.current_organization) may no longer be set on the DB connection.
    Any lazy-load of a relationship during response serialization would
    then fail.  This decorator catches those errors and returns a safe
    default so the response can still be serialized.
    """

    def decorator(method):
        @functools.wraps(method)
        def wrapper(self):
            try:
                return method(self)
            except (DetachedInstanceError, SQLAlchemyError) as exc:
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

    organization_id = Column(GUID(), ForeignKey("organization.id"), nullable=True)

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


class ReviewsMixin:
    """Mixin providing human-review properties over a JSONB reviews column.

    Subclasses must define:
        _reviews_column_name: str  — the JSONB column name (e.g. "test_reviews")
        _reviews_entity_type: str  — the entity-level target type (e.g. "test_result")
        _reviews_legacy_types: tuple[str, ...]  — legacy synonyms for the entity type
    """

    _reviews_column_name: str = ""
    _reviews_entity_type: str = ""
    _reviews_legacy_types: tuple = ()

    def _get_reviews_data(self):
        data = getattr(self, self._reviews_column_name, None)
        if not data or not isinstance(data, dict):
            return {}
        return data

    def _get_all_reviews(self):
        data = self._get_reviews_data()
        reviews = data.get("reviews", [])
        if not reviews or not isinstance(reviews, list):
            return []
        return reviews

    @staticmethod
    def _get_target_type_from_review(review, default_type):
        target = review.get("target") or {}
        return target.get("type", default_type)

    def _compute_review_state(self):
        """Single-pass over all reviews. Returns (last_review, matches_review, review_summary)."""
        reviews = self._get_all_reviews()
        if not reviews:
            return None, False, None

        entity_type = self._reviews_entity_type
        all_entity_types = (entity_type,) + self._reviews_legacy_types

        summary = {}
        entity_level = []

        for review in reviews:
            raw_type = self._get_target_type_from_review(review, entity_type)
            canonical_type = entity_type if raw_type in self._reviews_legacy_types else raw_type

            target = review.get("target") or {}
            reference = target.get("reference")
            key = f"{canonical_type}:{reference}" if reference else canonical_type
            ts = review.get("updated_at") or review.get("created_at") or ""
            existing = summary.get(key)
            _ex = existing or {}
            existing_ts = _ex.get("updated_at") or _ex.get("created_at") or ""
            if not existing or ts > existing_ts:
                summary[key] = {
                    "target_type": canonical_type,
                    "reference": reference,
                    "status": review.get("status"),
                    "user": review.get("user"),
                    "updated_at": ts,
                    "review_id": review.get("review_id"),
                }

            if raw_type in all_entity_types:
                entity_level.append(review)

        last_review = None
        if entity_level:
            last_review = max(
                entity_level,
                key=lambda r: r.get("updated_at") or r.get("created_at") or "",
            )

        matches = False
        if last_review:
            review_status = last_review.get("status")
            if review_status and isinstance(review_status, dict):
                review_status_id = review_status.get("status_id")
                status_id = self._get_status_id_for_match()
                if review_status_id and status_id:
                    matches = str(status_id) == str(review_status_id)

        return last_review, matches, summary if summary else None

    def _get_status_id_for_match(self):
        """Return the status UUID to compare against the review verdict."""
        return getattr(self, "status_id", None)

    @property
    def last_review(self):
        return self._compute_review_state()[0]

    @property
    def matches_review(self):
        return self._compute_review_state()[1]

    @property
    def review_summary(self):
        return self._compute_review_state()[2]


class EmbeddableMixin:
    """
    Mixin for entities that support vector embeddings and full-text search.

    Entities with this mixin must implement to_searchable_text() which defines
    what text should be:
    1. Indexed for full-text search (via Embedding.searchable_text -> tsv column)
    2. Used as source for generating vector embeddings

    The searchable text will be:
    - Stored in Embedding.searchable_text
    - Hashed to Embedding.text_hash (to detect changes)
    - Converted to tsvector in Embedding.tsv (for PostgreSQL full-text search)
    - Vectorized and stored in Embedding.embedding_{dimension} columns

    The mixin also provides a polymorphic `embeddings` relationship that automatically
    filters by the entity's class name.
    """

    @declared_attr
    def embeddings(cls):
        """Polymorphic embedding relationship"""
        return relationship(
            "Embedding",
            primaryjoin=(
                f"and_(Embedding.entity_id == foreign({cls.__name__}.id), "
                f"Embedding.entity_type == '{cls.__name__}')"
            ),
            foreign_keys="[Embedding.entity_id]",
            viewonly=True,
            uselist=True,
        )

    def searchable_text_changed(self, connection: Connection) -> bool:
        """
        Return True if embeddings should be (re)generated for this entity.
        - No rows in embedding yet -> True.
        - At least one row has text_hash matching current searchable text -> False.
        - Otherwise -> True.
        """
        searchable_text = self.to_searchable_text()
        current_hash = hashlib.sha256(searchable_text.encode("utf-8")).hexdigest()

        stmt = text("""
            SELECT EXISTS (
                SELECT 1
                FROM embedding
                WHERE entity_id = :entity_id
                  AND entity_type = :entity_type
                  AND text_hash = :text_hash
            )
        """)
        has_match = bool(
            connection.execute(
                stmt,
                {
                    "entity_id": self.id,
                    "entity_type": self.__class__.__name__,
                    "text_hash": current_hash,
                },
            ).scalar_one()
        )
        return not has_match

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
    session = object_session(target)
    if session is None:
        return
    pending = session.info.setdefault(_PENDING_EMBEDDING_JOBS_KEY, [])
    pending.append(
        {
            "entity_type": target.__class__.__name__,
            "entity_id": str(target.id),
            "user_id": str(target.user_id),
            "organization_id": str(target.organization_id),
        }
    )


@event.listens_for(Session, "after_commit")
def _process_pending_embedding_jobs(session: Session) -> None:
    jobs = session.info.pop(_PENDING_EMBEDDING_JOBS_KEY, None)
    if not jobs:
        return

    from rhesis.backend.app.database import get_db_with_tenant_variables
    from rhesis.backend.app.services.embedding.services import EmbeddingService

    for job in jobs:
        try:
            with get_db_with_tenant_variables(
                job["organization_id"],
                job["user_id"],
            ) as db:
                from rhesis.backend.app import models

                model_class = getattr(models, job["entity_type"], None)
                if model_class is None:
                    logger.warning(
                        "Skipping deferred embedding: unknown entity type %s",
                        job["entity_type"],
                    )
                    continue

                entity = db.query(model_class).filter(model_class.id == job["entity_id"]).first()
                if entity is None:
                    logger.warning(
                        "Skipping deferred embedding: entity not found %s %s",
                        job["entity_type"],
                        job["entity_id"],
                    )
                    continue

                if not hasattr(entity, "to_searchable_text"):
                    logger.warning(
                        "Skipping deferred embedding: %s does not implement to_searchable_text",
                        job["entity_type"],
                    )
                    continue

                searchable_text = entity.to_searchable_text()
                embedding_service = EmbeddingService(db)
                embedding_service.enqueue_embedding(
                    entity_type=job["entity_type"],
                    entity_id=job["entity_id"],
                    searchable_text=searchable_text,
                    user_id=job["user_id"],
                    organization_id=job["organization_id"],
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
        logger.warning(
            f"Skipping embedding for {target.__class__.__name__} {target.id}: user_id is None"
        )
        return

    try:
        _queue_embedding_after_commit(target)
    except Exception as e:
        logger.error(f"Error enqueuing embedding for {target.__class__.__name__} {target.id}: {e}")


@event.listens_for(EmbeddableMixin, "after_update", propagate=True)
def on_entity_update(mapper, connection, target):
    if getattr(target, "user_id", None) is None:
        logger.warning(
            f"Skipping embedding for {target.__class__.__name__} {target.id}: user_id is None"
        )
        return

    try:
        _queue_embedding_after_commit(target)
    except Exception as e:
        logger.error(f"Error enqueuing embedding for {target.__class__.__name__} {target.id}: {e}")
