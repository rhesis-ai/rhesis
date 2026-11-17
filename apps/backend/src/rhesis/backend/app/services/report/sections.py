"""Extension point for extra report sections.

Core builds the light report on its own: summary, requirements, runs. EE adds
sections (by impact, people, stats) by registering them here from its
:func:`~rhesis.backend.ee.bootstrap`, so core never imports EE code.

Contract
--------
A section has a unique ``key``, the :class:`FeatureName` that gates it, and a
``build`` callable. ``build(db, context)`` returns JSON-serializable data. Core
calls it only for organizations the feature is available to: live for a draft,
once at publish, after which the output is frozen in ``report.sections[key]`` and
covered by the snapshot hash. A Community build registers nothing, so
``report.sections`` stays empty.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple

from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.services.report.counting import CountedResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from rhesis.backend.app.models.organization import Organization
    from rhesis.backend.app.models.report import Report

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportContext:
    """What a section builds from: the report and the results it counts."""

    report: "Report"
    test_run_ids: Tuple[uuid.UUID, ...]
    requirement_ids: Tuple[uuid.UUID, ...]
    counted: Tuple[CountedResult, ...]


SectionBuilder = Callable[["Session", ReportContext], Any]


@dataclass(frozen=True)
class ReportSection:
    key: str
    feature: FeatureName
    build: SectionBuilder


_sections: Dict[str, ReportSection] = {}


def register_report_section(section: ReportSection) -> None:
    """Register *section*. Re-registering the same section is a no-op (re-bootstrap in
    tests); a different section under a taken key is a bug and raises."""
    existing = _sections.get(section.key)
    if existing is not None and existing != section:
        raise RuntimeError(f"A different report section is already registered as {section.key!r}")
    _sections[section.key] = section


def get_report_sections() -> List[ReportSection]:
    return list(_sections.values())


def build_sections(
    db: "Session",
    context: ReportContext,
    organization: "Organization",
    *,
    strict: bool,
) -> Dict[str, Any]:
    """Run every section the organization is entitled to.

    ``strict`` (publish) lets a failing section abort, so nothing half-built is
    frozen. A draft preview logs the failure and leaves that section out.
    """
    out: Dict[str, Any] = {}
    for section in _sections.values():
        if not FeatureRegistry.is_available(section.feature, organization):
            continue
        try:
            out[section.key] = section.build(db, context)
        except Exception:
            if strict:
                raise
            logger.exception(
                "report section %s failed for report %s", section.key, context.report.id
            )
    return out


def reset_report_sections() -> None:
    """Clear the registry. For tests that need a clean state."""
    _sections.clear()


__all__ = [
    "ReportContext",
    "ReportSection",
    "SectionBuilder",
    "build_sections",
    "get_report_sections",
    "register_report_section",
    "reset_report_sections",
]
