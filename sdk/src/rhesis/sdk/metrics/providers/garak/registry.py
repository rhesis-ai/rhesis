"""
Garak detector registry — loads definitions from ``detectors.yaml``.

Every garak detector that Rhesis supports is declared in the YAML file
shipped alongside this module.  The factory, metric class, tests, and
the backend's initial-data seeding all derive their lookup tables from
the parsed definitions exposed here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

_YAML_PATH = Path(__file__).with_name("detectors.yaml")


@dataclass(frozen=True)
class DetectorDef:
    """Immutable definition of a garak detector known to Rhesis."""

    name: str
    path: str
    display_name: str
    description: str
    explanation: str = ""
    behavior: str = "Compliance"
    required_note: Optional[str] = None
    external_service: bool = False
    legacy_aliases: Tuple[str, ...] = field(default_factory=tuple)


def _load_yaml(path: Path = _YAML_PATH) -> Tuple[Dict[str, Any], List[DetectorDef]]:
    """Parse ``detectors.yaml`` and return (defaults, detector_list)."""
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    defaults = raw.get("defaults", {})
    entries: List[DetectorDef] = []
    for item in raw.get("detectors", []):
        aliases = item.get("legacy_aliases") or []
        entries.append(
            DetectorDef(
                name=item["name"],
                path=item["path"],
                display_name=item["display_name"],
                description=item["description"],
                explanation=item.get("explanation", ""),
                behavior=item.get("behavior", "Compliance"),
                required_note=item.get("required_note"),
                external_service=item.get("external_service", False),
                legacy_aliases=tuple(aliases),
            )
        )
    return defaults, entries


# ── Loaded once at import time ───────────────────────────────────────────────

DEFAULTS, DETECTORS = _load_yaml()
DETECTORS: Tuple[DetectorDef, ...] = tuple(DETECTORS)  # type: ignore[no-redef]


# ── Derived lookup tables ────────────────────────────────────────────────────

NAME_TO_PATH: Dict[str, str] = {d.name: d.path for d in DETECTORS}

CONTEXT_REQUIRED_NOTES: Dict[str, str] = {
    d.path: d.required_note for d in DETECTORS if d.required_note
}

SUPPORTED_NAMES: List[str] = [d.name for d in DETECTORS]

LEGACY_ALIASES: Dict[str, str] = {alias: d.path for d in DETECTORS for alias in d.legacy_aliases}

DETECTOR_PATHS: Dict[str, Optional[str]] = {
    **NAME_TO_PATH,
    **LEGACY_ALIASES,
    "GarakDetectorMetric": None,
}

# ── Path helpers ─────────────────────────────────────────────────────────────


def normalize_detector_path(path: str) -> str:
    """Return a fully-qualified Garak detector path (``garak.detectors.…``).

    Garak's ``recommended_detector`` / ``primary_detector`` attributes and the
    value stored in ``Metric.evaluation_prompt`` in the DB can be either a
    short relative path (``encoding.DecodeMatch``) or a full path
    (``garak.detectors.encoding.DecodeMatch``).  This function normalises both
    forms to the canonical full form used as keys in ``CONTEXT_REQUIRED_NOTES``.
    """
    if not path.startswith("garak."):
        return f"garak.detectors.{path}"
    return path


def is_context_required(path: str) -> bool:
    """Return True if the detector identified by *path* requires probe context notes."""
    return normalize_detector_path(path) in CONTEXT_REQUIRED_NOTES


# ── Convenience subsets (used by tests) ──────────────────────────────────────

STANDALONE_DETECTORS: Dict[str, str] = {
    d.name: d.path for d in DETECTORS if d.required_note is None and not d.external_service
}

TRIGGER_DEPENDENT_DETECTORS: Dict[str, str] = {
    d.name: d.path for d in DETECTORS if d.required_note == "triggers"
}

REPEAT_WORD_DETECTORS: Dict[str, str] = {
    d.name: d.path for d in DETECTORS if d.required_note == "repeat_word"
}

EXTERNAL_SERVICE_DETECTORS: Dict[str, str] = {
    d.name: d.path for d in DETECTORS if d.external_service
}


# ── Helper for backend initial-data seeding ──────────────────────────────────


def to_initial_data_metrics() -> List[Dict[str, Any]]:
    """Build the ``metrics`` entries for the backend's initial-data loader.

    Merges per-detector fields from the YAML with the shared ``defaults``
    section so the backend doesn't have to duplicate any of this.
    """
    metrics: List[Dict[str, Any]] = []
    for d in DETECTORS:
        entry = {
            **DEFAULTS,
            "name": d.display_name,
            "description": d.description,
            "evaluation_prompt": d.path,
            "evaluation_steps": "[garak]",
            "reasoning": "[garak]",
            "explanation": d.explanation,
            "behaviors": [d.behavior],
        }
        metrics.append(entry)
    return metrics
