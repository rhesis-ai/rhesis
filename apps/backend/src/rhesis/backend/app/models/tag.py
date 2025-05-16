from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from .base import Base
from .guid import GUID
from .mixins import OrganizationAndUserMixin


class Tag(Base, OrganizationAndUserMixin):
    """
    This is the Tag table

    This is an example code on how to use it with other entities:

    ```python
    # Retrieve some tags from the database
    tag1 = session.query(Tag).filter_by(name="Technology").first()
    tag2 = session.query(Tag).filter_by(name="AI").first()

    # Create an item and assign tags directly
    item = Item(title="AI and the Future", description="An article about AI")
    item.tags = [tag1, tag2]  # Use the property directly

    session.add(item)
    session.commit()

    This is possible via the TagsMixin class.

    """

    __tablename__ = "tag"
    name = Column(String)
    icon_unicode = Column(String)  # Unicode character for the icon, e.g. 🎈
    tagged_items = relationship("TaggedItem", back_populates="tag")


class TaggedItem(Base, OrganizationAndUserMixin):
    __tablename__ = "tagged_item"

    tag_id = Column(GUID, ForeignKey("tag.id"), nullable=False)
    entity_id = Column(GUID, nullable=False)  # The ID of the related entity
    entity_type = Column(String, nullable=False)  # The type of the related entity

    # Relationship back to the Tag
    tag = relationship("Tag", back_populates="tagged_items")
