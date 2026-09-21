"""Workflow intents, loaded from the skill's canonical ``intents.yaml``.

The menu the agent shows, the signals it classifies with, and the references it
reads next are all one dataset. It lives with the skill because that is where it
is domain knowledge rather than agent plumbing, and it ships in the wheel through
the same ``skill_refs`` force-include as the reference markdown.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from rhesis.sdk.agents.architect.references import resolve_skills_references_dir

INTENTS_FILENAME = "intents.yaml"


class IntentsError(RuntimeError):
    """Raised when ``intents.yaml`` is missing or malformed."""


class WorkflowPath(StrEnum):
    """High-level user intent — drives which reference files load per turn.

    Coarser than the menu: quick and comprehensive exploration are one path
    because they read the same references. Every ``workflow_path`` in
    ``intents.yaml`` is one of these, and never ``UNSET`` — that means the agent
    has not classified the turn yet, so no intent may claim it.
    """

    UNSET = "unset"
    EXPLORE = "explore"
    PRD = "prd"
    RUN_ANALYZE = "run_analyze"
    DIRECT = "direct"


@dataclass(frozen=True)
class MenuEntry:
    """A numbered choice in the four-path menu."""

    number: int
    word: str
    label: str
    cues: Tuple[str, ...]
    phrases: Tuple[str, ...]


@dataclass(frozen=True)
class Intent:
    """One thing a user can ask for at the start of a session."""

    key: str
    name: str
    workflow_path: WorkflowPath
    description: str
    match_priority: int
    trigger_signals: Tuple[str, ...]
    keyword_signals: Tuple[str, ...]
    next_references: Tuple[str, ...]
    keyword_min_length: int = 0
    attachment_min_length: Optional[int] = None
    menu: Optional[MenuEntry] = None


def intents_path() -> Path:
    """Absolute path to the canonical intents file."""
    references = resolve_skills_references_dir()
    if references is None:
        raise IntentsError(
            "skill references directory not found — cannot load "
            f"{INTENTS_FILENAME}; set RHESIS_SKILLS_REFERENCES"
        )
    return references / INTENTS_FILENAME


def _require(raw: Dict[str, Any], field: str, key: str) -> Any:
    if field not in raw:
        raise IntentsError(f"intent '{key}' is missing required field '{field}'")
    return raw[field]


def _parse_menu(raw: Optional[Dict[str, Any]], key: str) -> Optional[MenuEntry]:
    if not raw:
        return None
    return MenuEntry(
        number=int(_require(raw, "number", key)),
        word=str(_require(raw, "word", key)),
        label=str(_require(raw, "label", key)),
        cues=tuple(raw.get("cues") or ()),
        phrases=tuple(raw.get("phrases") or ()),
    )


def _parse_workflow_path(raw: Any, key: str) -> WorkflowPath:
    """Reject a typo here rather than mid-conversation, when the path is used."""
    legal = [p.value for p in WorkflowPath if p is not WorkflowPath.UNSET]
    try:
        path = WorkflowPath(raw)
    except ValueError:
        raise IntentsError(
            f"intent '{key}' has workflow_path '{raw}'; expected one of {legal}"
        ) from None
    if path is WorkflowPath.UNSET:
        raise IntentsError(
            f"intent '{key}' claims workflow_path 'unset', which means unclassified; "
            f"expected one of {legal}"
        )
    return path


def _parse_intent(raw: Dict[str, Any]) -> Intent:
    key = str(raw.get("key") or "")
    if not key:
        raise IntentsError(f"intent entry has no 'key': {raw!r}")
    attachment_min = raw.get("attachment_min_length")
    return Intent(
        key=key,
        name=str(_require(raw, "name", key)),
        workflow_path=_parse_workflow_path(_require(raw, "workflow_path", key), key),
        description=str(raw.get("description", "")).strip(),
        match_priority=int(_require(raw, "match_priority", key)),
        trigger_signals=tuple(raw.get("trigger_signals") or ()),
        keyword_signals=tuple(str(s).lower() for s in (raw.get("keyword_signals") or ())),
        next_references=tuple(raw.get("next_references") or ()),
        keyword_min_length=int(raw.get("keyword_min_length") or 0),
        attachment_min_length=None if attachment_min is None else int(attachment_min),
        menu=_parse_menu(raw.get("menu"), key),
    )


@lru_cache(maxsize=1)
def load_intents() -> Tuple[Intent, ...]:
    """Every intent, ordered by ``match_priority`` (lowest first)."""
    path = intents_path()
    try:
        document = yaml.safe_load(path.read_text()) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise IntentsError(f"could not read {path}: {exc}") from exc

    entries = document.get("intents")
    if not isinstance(entries, list) or not entries:
        raise IntentsError(f"{path} has no 'intents' list")

    intents = tuple(_parse_intent(entry) for entry in entries)
    keys = [intent.key for intent in intents]
    if len(set(keys)) != len(keys):
        raise IntentsError(f"{path} has duplicate intent keys: {keys}")

    return tuple(sorted(intents, key=lambda intent: intent.match_priority))


@lru_cache(maxsize=1)
def menu_intents() -> Tuple[Intent, ...]:
    """Intents that appear in the menu, in menu order."""
    numbered = [intent for intent in load_intents() if intent.menu is not None]
    return tuple(sorted(numbered, key=lambda intent: intent.menu.number))


def intent_by_key(key: str) -> Optional[Intent]:
    """Look an intent up by its canonical key."""
    return next((intent for intent in load_intents() if intent.key == key), None)
