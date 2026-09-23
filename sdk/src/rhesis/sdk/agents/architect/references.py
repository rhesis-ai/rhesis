"""Locate the shared skill references bundled with (or beside) the SDK."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_ARCHITECT_DIR = Path(__file__).resolve().parent
_SKILLS_REFERENCES_SUFFIX = Path("skills") / "rhesis" / "references"


def resolve_skills_references_dir() -> Optional[Path]:
    """Return skill reference markdown for Architect prompt includes.

    Resolution order:
    1. ``RHESIS_SKILLS_REFERENCES`` env override
    2. Monorepo ``skills/rhesis/references`` (walk up from this module)
    3. Bundled ``prompt_templates/skill_refs`` (populated at wheel build)
    """
    override = os.environ.get("RHESIS_SKILLS_REFERENCES", "").strip()
    if override:
        path = Path(override)
        return path if path.is_dir() else None

    current = _ARCHITECT_DIR
    for _ in range(12):
        references = current / _SKILLS_REFERENCES_SUFFIX
        if references.is_dir():
            return references
        if current.parent == current:
            break
        current = current.parent

    bundled = _ARCHITECT_DIR / "prompt_templates" / "skill_refs"
    if bundled.is_dir():
        return bundled

    logger.warning(
        "skills/rhesis/references not found — Architect prompt includes may be incomplete"
    )
    return None
