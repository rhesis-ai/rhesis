from nanoid import generate
from sqlalchemy import (
    TIMESTAMP,
    Column,
    String,
    func,
    text,
)
from sqlalchemy.orm import as_declarative, declared_attr

from rhesis.backend.app.models.guid import GUID

# Define a custom alphabet without underscores
custom_alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


@as_declarative()
class Base:
    id = Column(
        GUID(), primary_key=True, index=True, unique=True, server_default=text("gen_random_uuid()")
    )
    nano_id = Column(String, default=lambda: generate(size=12, alphabet=custom_alphabet))
    created_at = Column(TIMESTAMP, server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now(), nullable=False)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()
