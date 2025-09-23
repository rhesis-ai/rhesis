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
        return [tagged_item.tag for tagged_item in self._tags_relationship]

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


class CommentTaskMixin:
    """Mixin that provides polymorphic comment and task relationships with counts"""

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

    @property
    def counts(self):
        """Get the counts of comments and tasks for this entity"""
        return {
            "comments": len(self.comments) if self.comments else 0,
            "tasks": len(self.tasks) if self.tasks else 0,
        }


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


# For entities that need both
class OrganizationAndUserMixin(OrganizationMixin, UserOwnedMixin):
    """Mixin for both organization and user ownership"""

    pass
