"""Bookkeeping for the text extracted from an uploaded file.

Extraction itself (OCR, vision models) can take minutes, so callers hold no
database session while it runs. These helpers each take a short session.
"""

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from rhesis.backend.app.models.file import File

EXTRACTABLE_PREFIXES = ("image/", "application/pdf", "text/")


def _file(db: Session, file_id: str) -> Optional[File]:
    return db.query(File).filter(File.id == uuid.UUID(file_id)).first()


def needs_extraction(db: Session, file_id: str, content_type: str) -> bool:
    """Whether the file still needs extracting. Marks other types not applicable."""
    file_row = _file(db, file_id)
    if file_row is None or file_row.extraction_status == "done":
        return False
    if not content_type.startswith(EXTRACTABLE_PREFIXES):
        file_row.extraction_status = "not_applicable"
        db.commit()
        return False
    return True


def record_extraction(
    db: Session, file_id: str, status: str, extracted_text: Optional[str] = None
) -> bool:
    """Store the outcome. False when the row is gone or another run already finished it."""
    file_row = _file(db, file_id)
    if file_row is None or file_row.extraction_status == "done":
        return False
    if status == "done":
        file_row.extracted_text = extracted_text
    file_row.extraction_status = status
    db.commit()
    return True
