"""Pydantic validation for the two JSONB dicts Explorer reads and writes directly:
``Test.test_metadata`` and ``TestSet.attributes["adaptive_settings"]``.

Both columns are shared with non-explorer writers (garak sync/import, general test-set
attribute generation), so the models here use ``extra="allow"`` -- an unrecognized shape
must round-trip losslessly, not raise and not silently drop keys.

Pure schema module, no ORM imports, so it's importable from ``crud/``, ``services/explorer/``,
and ``services/test_set.py`` without layering violations.

Contract:

- Every ``parse_*`` function is **total** -- it never raises. ``None``, ``{}``, a non-mapping,
  or a garbage-shaped mapping all come back as an empty (all-defaults) model. The lenient
  ``mode="before"`` validators on each model make a ``ValidationError`` unreachable in
  practice; the ``try/except`` in each ``parse_*`` is the backstop that guarantees a
  foreign-shaped row (e.g. garak) can never crash an explorer endpoint.
- Dumping back to a JSONB-safe dict is always ``model.model_dump(mode="json", exclude_none=True)``,
  done at the call site rather than through a wrapper. ``mode="json"`` turns non-JSON-native types
  (e.g. ``UUID``) into strings. ``exclude_none=True`` makes "field is ``None``" round-trip as "key
  absent", reproducing the ``del meta["evaluation"]`` / ``meta.pop("metrics", None)`` idioms the
  call sites used before this module existed. This also means a foreign key explicitly set to
  ``null`` today would come back absent after a round trip through here -- no known caller does
  that, but it's worth knowing.
"""

import logging
from typing import Any, Dict, Final, List, Literal, Mapping, Optional, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from rhesis.backend.app.constants import EXPLORER_BEHAVIOR_NAME
from rhesis.backend.app.utils.uuid_utils import sanitize_uuid_field

logger = logging.getLogger(__name__)

ExplorerLabel = Literal["", "topic_marker", "pass", "fail", "error"]
TOPIC_MARKER_LABEL: Final[str] = "topic_marker"
_VALID_LABELS = set(get_args(ExplorerLabel))


def _coerce_label(value: Any) -> str:
    return value if isinstance(value, str) and value in _VALID_LABELS else ""


def _coerce_optional_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _coerce_model_score(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class ExplorerMetricEvalDetail(BaseModel):
    """Per-metric evaluation row (keyed by metric name on the parent model)."""

    model_config = ConfigDict(extra="allow")

    score: float
    is_successful: bool
    reason: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ExplorerEvaluationEntry(BaseModel):
    """One row of ``test_metadata["evaluation"]`` -- a per-metric verdict breakdown."""

    model_config = ConfigDict(extra="allow")

    label: ExplorerLabel = ""
    labeler: str = ""
    model_score: float = 0.0

    @field_validator("label", mode="before")
    @classmethod
    def _validate_label(cls, v: Any) -> str:
        return _coerce_label(v)

    @field_validator("labeler", mode="before")
    @classmethod
    def _validate_labeler(cls, v: Any) -> str:
        return "" if v is None else str(v)

    @field_validator("model_score", mode="before")
    @classmethod
    def _validate_model_score(cls, v: Any) -> float:
        return _coerce_model_score(v)


class ExplorerTestMetadata(BaseModel):
    """``Test.test_metadata`` for explorer-owned rows.

    ``output``/``labeler`` are ``Optional[str]`` rather than ``str`` so that "key absent"
    (``None``) stays distinguishable from "key present but empty" (``""``) -- callers that
    need a default only for the missing case (e.g. ``NO_OUTPUT``, ``"imported"``) rely on
    that distinction.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    output: Optional[str] = None
    label: ExplorerLabel = ""
    labeler: Optional[str] = None
    model_score: float = 0.0
    metrics: Optional[Dict[str, ExplorerMetricEvalDetail]] = None
    evaluation: Optional[List[ExplorerEvaluationEntry]] = None

    @field_validator("label", mode="before")
    @classmethod
    def _validate_label(cls, v: Any) -> str:
        return _coerce_label(v)

    @field_validator("output", "labeler", mode="before")
    @classmethod
    def _validate_optional_str(cls, v: Any) -> Optional[str]:
        return _coerce_optional_str(v)

    @field_validator("model_score", mode="before")
    @classmethod
    def _validate_model_score(cls, v: Any) -> float:
        return _coerce_model_score(v)

    @field_validator("metrics", mode="before")
    @classmethod
    def _validate_metrics(cls, v: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(v, dict):
            return None
        cleaned: Dict[str, Any] = {}
        for name, entry in v.items():
            if not isinstance(entry, dict):
                logger.warning("Dropping non-dict explorer metric entry %r", name)
                continue
            try:
                ExplorerMetricEvalDetail.model_validate(entry)
            except ValidationError:
                logger.warning("Dropping invalid explorer metric entry %r", name)
                continue
            cleaned[name] = entry
        return cleaned or None

    @field_validator("evaluation", mode="before")
    @classmethod
    def _validate_evaluation(cls, v: Any) -> Optional[List[Any]]:
        if not isinstance(v, list):
            return None
        cleaned = [entry for entry in v if isinstance(entry, dict)]
        return cleaned or None

    @property
    def is_topic_marker(self) -> bool:
        return self.label == TOPIC_MARKER_LABEL

    @classmethod
    def topic_marker(cls, labeler: str = "user") -> "ExplorerTestMetadata":
        return cls(label=TOPIC_MARKER_LABEL, labeler=labeler, output="")


class ExplorerAdaptiveSettings(BaseModel):
    """``TestSet.attributes["adaptive_settings"]``."""

    model_config = ConfigDict(extra="allow", validate_assignment=True)

    default_endpoint_id: Optional[UUID] = None

    @field_validator("default_endpoint_id", mode="before")
    @classmethod
    def _validate_default_endpoint_id(cls, v: Any) -> Optional[str]:
        return sanitize_uuid_field(v)


class ExplorerTestSetAttributeMetadata(BaseModel):
    """``TestSet.attributes["metadata"]`` -- the general behaviors/metadata blob."""

    model_config = ConfigDict(extra="allow")

    behaviors: List[str] = Field(default_factory=list)

    @field_validator("behaviors", mode="before")
    @classmethod
    def _validate_behaviors(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            return []
        return [item for item in v if isinstance(item, str)]


class ExplorerTestSetAttributes(BaseModel):
    """Read-only view of ``TestSet.attributes`` -- never dumped/round-tripped as a whole."""

    model_config = ConfigDict(extra="allow")

    metadata: Optional[ExplorerTestSetAttributeMetadata] = None
    adaptive_settings: Optional[ExplorerAdaptiveSettings] = None

    @property
    def is_explorer(self) -> bool:
        behaviors = self.metadata.behaviors if self.metadata else []
        return EXPLORER_BEHAVIOR_NAME in behaviors

    @property
    def default_endpoint_id(self) -> Optional[UUID]:
        return self.adaptive_settings.default_endpoint_id if self.adaptive_settings else None


def parse_explorer_test_metadata(raw: Optional[Mapping[str, Any]]) -> ExplorerTestMetadata:
    """Parse ``Test.test_metadata``. Never raises -- see module docstring."""
    try:
        return ExplorerTestMetadata.model_validate(raw or {})
    except ValidationError:
        logger.warning("Failed to parse explorer test metadata %r; using defaults", raw)
        return ExplorerTestMetadata()


def parse_explorer_adaptive_settings(
    raw: Optional[Mapping[str, Any]],
) -> ExplorerAdaptiveSettings:
    """Parse ``TestSet.attributes["adaptive_settings"]``. Never raises -- see module docstring."""
    try:
        return ExplorerAdaptiveSettings.model_validate(raw or {})
    except ValidationError:
        logger.warning("Failed to parse explorer adaptive settings %r; using defaults", raw)
        return ExplorerAdaptiveSettings()


def parse_explorer_test_set_attributes(
    raw: Optional[Mapping[str, Any]],
) -> ExplorerTestSetAttributes:
    """Parse ``TestSet.attributes``. Never raises -- see module docstring."""
    try:
        return ExplorerTestSetAttributes.model_validate(raw or {})
    except ValidationError:
        logger.warning("Failed to parse explorer test set attributes %r; using defaults", raw)
        return ExplorerTestSetAttributes()
