"""Column mapping for file import.

Provides heuristic auto-mapping and LLM-based fallback for mapping
source file columns to the expected test data schema.
"""

import os
from typing import Any, Dict, List, Optional

from jinja2 import Template
from pydantic import BaseModel, Field

from rhesis.backend.logging import logger

# Target fields the user's columns need to map to
TARGET_FIELDS = [
    "category",
    "topic",
    "behavior",
    "prompt_content",
    "expected_response",
    "language_code",
    "test_type",
    "test_configuration",
    # Multi-turn test configuration fields
    "goal",
    "instructions",
    "restrictions",
    "scenario",
    "metadata",
]

# Known aliases for each target field (lowercase)
_ALIASES: Dict[str, List[str]] = {
    "category": [
        "category",
        "cat",
        "test_category",
        "category_name",
        "type",
    ],
    "topic": [
        "topic",
        "test_topic",
        "topic_name",
        "subject",
    ],
    "behavior": [
        "behavior",
        "behaviour",
        "test_behavior",
        "behavior_name",
    ],
    "prompt_content": [
        "prompt_content",
        "prompt",
        "content",
        "question",
        "input",
        "text",
        "message",
        "user_message",
        "query",
        "test_prompt",
    ],
    "expected_response": [
        "expected_response",
        "expected",
        "answer",
        "response",
        "expected_output",
        "ground_truth",
        "reference",
        "target",
        "ideal",
    ],
    "language_code": [
        "language_code",
        "language",
        "lang",
        "locale",
    ],
    "test_type": [
        "test_type",
        "type",
        "turn_type",
    ],
    "test_configuration": [
        "test_configuration",
        "configuration",
        "config",
    ],
    "goal": [
        "goal",
        "objective",
        "target",
        "aim",
        "test_goal",
    ],
    "instructions": [
        "instructions",
        "instruction",
        "steps",
        "procedure",
        "test_instructions",
    ],
    "restrictions": [
        "restrictions",
        "restriction",
        "constraints",
        "limits",
        "forbidden",
        "test_restrictions",
    ],
    "scenario": [
        "scenario",
        "context",
        "situation",
        "setting",
        "test_scenario",
    ],
    "metadata": [
        "metadata",
        "meta",
        "extra",
        "attributes",
        "notes",
    ],
}


def auto_map_columns(
    headers: List[str],
) -> Dict[str, Any]:
    """Heuristic auto-mapping of source columns to target fields.

    Returns:
        {
            "mapping": {"source_col": "target_field", ...},
            "confidence": float 0.0-1.0,
            "unmatched_headers": ["col_a", ...],
            "unmatched_targets": ["field_b", ...],
        }
    """
    mapping: Dict[str, str] = {}
    matched_targets: set = set()

    # Normalize headers for comparison
    normalized = {h: h.strip().lower().replace(" ", "_") for h in headers}

    for header, norm in normalized.items():
        if norm in matched_targets:
            continue  # already mapped a different header to this target
        for target, aliases in _ALIASES.items():
            if target in matched_targets:
                continue
            if norm in aliases:
                mapping[header] = target
                matched_targets.add(target)
                break

    # Also handle nested JSON keys like "prompt.content"
    for header, norm in normalized.items():
        if header in mapping:
            continue
        if norm == "prompt.content":
            if "prompt_content" not in matched_targets:
                mapping[header] = "prompt_content"
                matched_targets.add("prompt_content")
        elif norm == "prompt.expected_response":
            if "expected_response" not in matched_targets:
                mapping[header] = "expected_response"
                matched_targets.add("expected_response")
        elif norm == "prompt.language_code":
            if "language_code" not in matched_targets:
                mapping[header] = "language_code"
                matched_targets.add("language_code")

    # Calculate confidence based on core fields matched
    # For single-turn: category, topic, behavior, prompt_content
    # For multi-turn: category, topic, behavior, goal
    single_turn_core = {"category", "topic", "behavior", "prompt_content"}
    multi_turn_core = {"category", "topic", "behavior", "goal"}

    single_turn_matched = single_turn_core & matched_targets
    multi_turn_matched = multi_turn_core & matched_targets

    # Use the better of the two confidences (in case it's ambiguous which type)
    single_confidence = len(single_turn_matched) / len(single_turn_core)
    multi_confidence = len(multi_turn_matched) / len(multi_turn_core)
    confidence = max(single_confidence, multi_confidence)

    unmatched_headers = [h for h in headers if h not in mapping]
    unmatched_targets = [t for t in TARGET_FIELDS if t not in matched_targets]

    return {
        "mapping": mapping,
        "confidence": confidence,
        "unmatched_headers": unmatched_headers,
        "unmatched_targets": unmatched_targets,
    }


# ── LLM-based mapping ───────────────────────────────────────────


class ImportMappingOutput(BaseModel):
    """Structured output schema for LLM import mapping."""

    mapping: Dict[str, str] = Field(
        description=(
            "Map from source column name to target field name. "
            "Target fields: category, topic, behavior, "
            "prompt_content, expected_response, language_code, "
            "test_type, test_configuration, goal, instructions, restrictions, scenario, metadata"
        )
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0 for the mapping",
    )
    reasoning: str = Field(
        description="Brief explanation of mapping choices",
    )


def is_llm_available(
    db: Optional[Any] = None,
    user: Optional[Any] = None,
) -> bool:
    """Check whether an LLM is available for mapping assistance.

    Returns False if db/user are missing or if the user has no
    generation model configured and the default model cannot be
    instantiated.  This allows callers to skip the LLM path
    entirely instead of waiting for it to fail.
    """
    if db is None or user is None:
        return False
    try:
        from rhesis.backend.app.utils.user_model_utils import (
            get_user_generation_model,
        )
        from rhesis.sdk.models.factory import get_model

        model_or_provider = get_user_generation_model(db, user)
        if isinstance(model_or_provider, str):
            # Verify the default provider can actually be instantiated
            get_model(provider=model_or_provider)
        return True
    except Exception:
        return False


def llm_map_columns(
    headers: List[str],
    sample_rows: List[Dict[str, Any]],
    db: Optional[Any] = None,
    user: Optional[Any] = None,
) -> Dict[str, Any]:
    """Use LLM to suggest column mapping.

    If no LLM is available (no db/user, no configured model, or
    the provider cannot be instantiated) this silently falls back
    to the heuristic auto-mapper -- no error is raised.
    """
    if not is_llm_available(db, user):
        logger.info("No LLM available for import mapping; using heuristic auto-mapper only")
        return auto_map_columns(headers)

    try:
        from rhesis.backend.app.utils.user_model_utils import (
            get_user_generation_model,
        )
        from rhesis.sdk.models.factory import get_model

        model_or_provider = get_user_generation_model(db, user)
        if isinstance(model_or_provider, str):
            model = get_model(provider=model_or_provider)
        else:
            model = model_or_provider

        template_path = os.path.join(os.path.dirname(__file__), "mapping_prompt.jinja")
        with open(template_path, "r") as f:
            prompt_template = Template(f.read())

        prompt = prompt_template.render(
            headers=headers,
            sample_rows=sample_rows[:3],
            target_fields=TARGET_FIELDS,
        )

        response = model.generate(
            prompt=prompt,
            schema=ImportMappingOutput,
            temperature=0.1,
        )

        if isinstance(response, dict):
            result = response
        else:
            result = response.model_dump() if hasattr(response, "model_dump") else response

        logger.info(f"LLM import mapping confidence: {result['confidence']:.2f}")
        return result

    except Exception as e:
        logger.warning(
            f"LLM import mapping failed, using heuristic: {e}",
        )
        return auto_map_columns(headers)
