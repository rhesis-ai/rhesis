from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import OrganizationAndUserMixin


class Source(Base, OrganizationAndUserMixin):
    __tablename__ = "source"

    title = Column(String, nullable=False)  # Source name or title, required
    description = Column(Text)  # Optional description of the source
    entity_type = Column(String)  # Type of entity (e.g., 'website', 'paper')
    url = Column(String)  # Optional, URL if the source is a website
    citation = Column(Text)  # Optional, citation details for papers or books
    language_code = Column(
        String(5), comment="Language in IETF language tag format"
    )  # Language of the source (e.g., 'en-US')
    prompt_templates = relationship("PromptTemplate", back_populates="source")
    prompts = relationship("Prompt", back_populates="source")
