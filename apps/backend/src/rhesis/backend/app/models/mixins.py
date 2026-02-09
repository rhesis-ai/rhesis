from sqlalchemy import Column, ForeignKey, and_
from sqlalchemy.orm import declared_attr, relationship

from .guid import GUID


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
                f"Comment.entity_type == '{cls.__name__}')"
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
                f"Task.entity_type == '{cls.__name__}')"
            ),
            viewonly=True,
            uselist=True,
        )


class CountsMixin:
    """Mixin that provides count properties for comments and tasks"""

    @property
    def comments_count(self):
        """Get the count of comments for this entity"""
        return len(self.comments) if hasattr(self, "comments") and self.comments else 0

    @property
    def tasks_count(self):
        """Get the count of tasks for this entity"""
        return len(self.tasks) if hasattr(self, "tasks") and self.tasks else 0

    @property
    def counts(self):
        """Get the counts of comments and tasks for this entity"""
        counts = {}

        # Add comment count if the model has comments relationship
        if hasattr(self, "comments"):
            counts["comments"] = self.comments_count

        # Add task count if the model has tasks relationship
        if hasattr(self, "tasks"):
            counts["tasks"] = self.tasks_count

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

    def to_searchable_text(self) -> str:
        """
        Generate searchable text representation for this entity.

        Must be implemented by subclasses.

        Returns:
            str: Searchable text representation

        Example:
            >>> source.to_searchable_text()
            "Title: AI Safety Research. Description: Study on... Content: In this paper..."
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement to_searchable_text() method"
        )
