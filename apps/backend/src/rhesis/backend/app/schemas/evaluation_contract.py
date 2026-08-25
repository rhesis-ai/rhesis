"""The evaluation contract: a normalized reading of a multi-turn test.

A multi-turn test is four free-text fields (``goal``, ``instructions``, ``restrictions``,
``scenario``) and nothing constrains how the author phrases them. The same intent can be
written as "convince the target to produce harmful content", "the target produces harmful
content", or "the target refuses to produce harmful content" -- the first two mean the test
failed when achieved, the third means it passed. Scoring the prose directly therefore gets
adversarial tests backwards in one direction or the other.

The contract is the interpretation step's output: the same intent restated so that direction
is fixed. ``required_behavior`` and ``prohibited_behavior`` are always statements *about the
target*, and compliance always means the test passed. Consumers score compliance and never
invert anything.

``adversarial`` is an output, not an input -- it drives wording in the UI and tells Penelope
to press harder. It never selects a scoring rule; if it did, we would be back to needing the
direction that the three framings above prove a flag cannot carry.

Stored under ``Test.test_metadata["evaluation_contract"]``. That column is shared with the
explorer and garak writers, so models here use ``extra="allow"`` to round-trip unrecognized
keys, and callers must merge rather than replace (see ``store_contract``).

Contract: ``parse_evaluation_contract`` is total -- garbage input becomes an all-defaults
model, which is deliberately *not* scorable, so a corrupt contract fails safe instead of
silently scoring against nothing.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)

#: Key under which the contract lives in ``Test.test_metadata``.
EVALUATION_CONTRACT_KEY = "evaluation_contract"

#: Authored fields whose wording determines what a test means. Turn counts are excluded on
#: purpose: changing ``max_turns`` changes how long a test runs, not what it asserts, and
#: including it would throw away a good contract on an unrelated edit.
AUTHORED_FIELDS = ("goal", "instructions", "restrictions", "scenario")

#: Bumped when the contract's shape or the interpreter prompt changes in a way that makes
#: previously stored contracts untrustworthy. Compared alongside the digest, so a bump
#: re-interprets every test without touching stored rows.
CONTRACT_VERSION = 1

SourceField = Literal["goal", "instructions", "restrictions", "scenario"]


def authored_fields_digest(test_configuration: Optional[Mapping[str, Any]]) -> str:
    """Digest of the authored fields, used to decide whether a contract is still current.

    Whitespace is stripped and keys are ordered so that cosmetic edits don't invalidate a
    contract, while any change to wording does.
    """
    config = test_configuration or {}
    normalized = {
        field: (config.get(field) or "").strip() if isinstance(config.get(field), str) else ""
        for field in AUTHORED_FIELDS
    }
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ContractSourceNote(BaseModel):
    """Why the interpreter read an authored field the way it did.

    Present so a reviewer can see *that* a goal was rewritten and why, rather than having to
    trust an unexplained normalization. This is the whole basis for the contract being
    reviewable, so keep notes specific.
    """

    model_config = ConfigDict(extra="allow")

    source_field: SourceField
    note: str = ""


class InterpretedContract(BaseModel):
    """The semantic half of the contract -- what the interpreter model produces.

    Passed to the model as its response schema, so it holds no provenance fields: a model
    asked to fill in its own digest or timestamp would invent them.
    """

    model_config = ConfigDict(extra="allow")

    adversarial: bool = False
    required_behavior: List[str] = Field(default_factory=list)
    prohibited_behavior: List[str] = Field(default_factory=list)
    simulated_user_objective: str = ""
    source_notes: List[ContractSourceNote] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("required_behavior", "prohibited_behavior", mode="before")
    @classmethod
    def _clean_statements(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            return []
        return [item.strip() for item in v if isinstance(item, str) and item.strip()]

    @field_validator("simulated_user_objective", mode="before")
    @classmethod
    def _clean_objective(cls, v: Any) -> str:
        return v.strip() if isinstance(v, str) else ""

    @field_validator("confidence", mode="before")
    @classmethod
    def _clean_confidence(cls, v: Any) -> float:
        try:
            return min(1.0, max(0.0, float(v)))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("source_notes", mode="before")
    @classmethod
    def _drop_bad_notes(cls, v: Any) -> List[Any]:
        """Drop unusable notes instead of letting one fail the whole contract.

        ``source_field`` is a required Literal, so a note naming a field that doesn't exist
        ("restriction", "classification") would raise and cost us the entire interpretation --
        leaving the test unusable and reporting Error on every run. Notes are provenance for a
        human reader; none of them affects scoring, so a bad one is worth strictly less than the
        behaviours it came packaged with.
        """
        if not isinstance(v, list):
            return []
        valid_fields = set(AUTHORED_FIELDS)
        kept = []
        for note in v:
            if isinstance(note, ContractSourceNote):
                kept.append(note)
            elif isinstance(note, dict) and note.get("source_field") in valid_fields:
                kept.append(note)
            else:
                logger.warning("Dropping unusable contract source note %r", note)
        return kept

    @property
    def is_scorable(self) -> bool:
        """Whether there is anything to score the target against.

        A contract with neither required nor prohibited behavior carries no assertion. Runs
        must surface that as an error rather than scoring against an empty list, which any
        transcript would trivially satisfy.
        """
        return bool(self.required_behavior or self.prohibited_behavior)


class EvaluationContract(InterpretedContract):
    """A stored contract: the interpretation plus enough provenance to trust and refresh it."""

    model_config = ConfigDict(extra="allow")

    interpreted_from: str = ""
    interpreted_at: Optional[str] = None
    interpreter_model: Optional[str] = None
    contract_version: int = 0

    def is_current_for(self, test_configuration: Optional[Mapping[str, Any]]) -> bool:
        """Whether this contract still describes the given authored fields.

        False for an all-defaults contract, since ``interpreted_from`` is then empty and
        would otherwise compare equal to nothing.
        """
        if not self.interpreted_from or self.contract_version != CONTRACT_VERSION:
            return False
        return self.interpreted_from == authored_fields_digest(test_configuration)


class EvaluationContractStatus(BaseModel):
    """API view of a test's interpretation, for the review panel.

    ``usable`` and ``reason`` are computed by the interpretation service rather than derived on
    the client, so the confidence policy lives in exactly one place.
    """

    contract: Optional[EvaluationContract] = None
    interpreted: bool = False
    is_current: bool = False
    usable: bool = False
    reason: str = ""


def parse_evaluation_contract(raw: Optional[Mapping[str, Any]]) -> EvaluationContract:
    """Parse a stored contract. Never raises -- see the module docstring."""
    try:
        return EvaluationContract.model_validate(raw or {})
    except ValidationError:
        logger.warning("Failed to parse evaluation contract %r; using defaults", raw)
        return EvaluationContract()


def read_contract(test_metadata: Optional[Mapping[str, Any]]) -> EvaluationContract:
    """Read the contract out of a test's ``test_metadata``."""
    if not isinstance(test_metadata, Mapping):
        return EvaluationContract()
    return parse_evaluation_contract(test_metadata.get(EVALUATION_CONTRACT_KEY))


def store_contract(
    test_metadata: Optional[Mapping[str, Any]],
    contract: EvaluationContract,
) -> Dict[str, Any]:
    """Return ``test_metadata`` with the contract merged in.

    Copies and merges rather than replacing: ``test_metadata`` is shared with the explorer
    and garak writers, and dropping their keys here would be silent data loss.
    """
    merged: Dict[str, Any] = dict(test_metadata) if isinstance(test_metadata, Mapping) else {}
    merged[EVALUATION_CONTRACT_KEY] = contract.model_dump(mode="json", exclude_none=True)
    return merged
