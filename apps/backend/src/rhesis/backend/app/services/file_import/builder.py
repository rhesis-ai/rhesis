"""TestData payload builder for file import.

Converts normalised row dicts into the TestData payload format consumed
by bulk_create_test_set, including turn-config value parsing.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def parse_turn_config(value: str) -> Optional[Tuple[Optional[int], Optional[int]]]:
    """Parse a turn-config value into (min_turns, max_turns).

    Either element may be None when only one bound is specified.

    Supported formats:
    - "3"              → (3, 3)         single integer → exact turn count
    - "3 turns"        → (3, 3)         with unit word
    - "2-5"            → (2, 5)         hyphen/en-dash range
    - "2–5"            → (2, 5)         em-dash range
    - "2 to 5"         → (2, 5)         word range
    - "2..5"           → (2, 5)         dot range
    - "min 2, max 5"   → (2, 5)         labelled pair (comma or space separated)
    - "min:2 max:5"    → (2, 5)         colon-labelled pair
    - "max 5"          → (None, 5)      max only
    - "max:5"          → (None, 5)
    - "min 2"          → (2, None)      min only
    - "min:2"          → (2, None)

    Returns None if the value cannot be parsed.
    """
    v = value.strip().lower()

    # Labelled pair: "min 2, max 5" / "min:2 max:5" / "min=2,max=5" etc.
    min_match = re.search(r"min\s*[=:]\s*(\d+)", v)
    max_match = re.search(r"max\s*[=:]\s*(\d+)", v)
    # Also accept bare "min 2" / "max 5" (space separator, no punctuation)
    if not min_match:
        min_match = re.search(r"\bmin\s+(\d+)", v)
    if not max_match:
        max_match = re.search(r"\bmax\s+(\d+)", v)

    if min_match or max_match:
        min_v = int(min_match.group(1)) if min_match else None
        max_v = int(max_match.group(1)) if max_match else None
        return min_v, max_v

    # Range formats: "2-5", "2–5", "2 - 5", "2..5", "2 to 5"
    range_match = re.match(r"^(\d+)\s*(?:[-–]|\.\.|\bto\b)\s*(\d+)$", v)
    if range_match:
        return int(range_match.group(1)), int(range_match.group(2))

    # Single integer, optionally followed by a unit word ("3", "3 turns", "3 turn")
    single_match = re.match(r"^(\d+)(?:\s+turns?)?$", v)
    if single_match:
        n = int(single_match.group(1))
        return n, n

    return None


def rows_to_test_data(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert normalized rows to the TestData payload format.

    Filters out rows that are completely empty (no category, topic,
    behavior, or prompt content). Multi-turn tests don't require a prompt.
    """
    tests = []
    for row in rows:
        prompt = row.get("prompt", {})
        prompt_content = prompt.get("content", "") if isinstance(prompt, dict) else ""
        category = row.get("category", "")
        topic = row.get("topic", "")
        behavior = row.get("behavior", "")
        test_type = row.get("test_type", "Single-Turn")

        is_multi_turn = test_type == "Multi-Turn"

        # Skip completely empty rows
        if is_multi_turn:
            if not any(str(v or "").strip() for v in [category, topic, behavior]):
                continue
        else:
            if not any(str(v or "").strip() for v in [prompt_content, category, topic, behavior]):
                continue

        # Build a clean prompt dict — multi-turn tests don't have prompts
        clean_prompt = None
        if not is_multi_turn and isinstance(prompt, dict):
            clean_prompt = dict(prompt)
            pc = clean_prompt.get("content")
            if isinstance(pc, dict) and "content" in pc:
                clean_prompt.update(pc)
            elif isinstance(pc, dict):
                clean_prompt["content"] = str(pc)

        test: Dict[str, Any] = {
            "category": category or "Uncategorized",
            "topic": topic or "General",
            "behavior": behavior or "Default",
        }

        if clean_prompt is not None and clean_prompt.get("content"):
            test["prompt"] = clean_prompt

        if row.get("test_type"):
            test["test_type"] = row["test_type"]

        # Build test_configuration from a pre-built dict or from separate fields
        config_raw = row.get("test_configuration")
        if config_raw is not None:
            if isinstance(config_raw, str):
                try:
                    config_raw = json.loads(config_raw)
                except json.JSONDecodeError:
                    config_raw = None
            if isinstance(config_raw, dict):
                test["test_configuration"] = config_raw

        if "test_configuration" not in test:
            test_config: Dict[str, Any] = {}
            for field in ("goal", "instructions", "restrictions", "scenario"):
                if row.get(field):
                    test_config[field] = row[field]

            raw_min = row.get("min_turns")
            if raw_min is not None and str(raw_min).strip():
                test_config["min_turns"] = int(raw_min)

            raw_max = row.get("max_turns")
            if raw_max is not None and str(raw_max).strip():
                # Support range "2-5" → min_turns=2, max_turns=5;
                # single value "3" → min_turns=3, max_turns=3.
                parsed = parse_turn_config(str(raw_max).strip())
                if parsed is not None:
                    min_v, max_v = parsed
                    if min_v is not None and "min_turns" not in test_config:
                        test_config["min_turns"] = min_v
                    if max_v is not None:
                        test_config["max_turns"] = max_v

            if test_config:
                test["test_configuration"] = test_config

        if row.get("metadata"):
            meta = row["metadata"]
            test["metadata"] = meta if isinstance(meta, dict) else {"notes": str(meta)}

        tests.append(test)

    return tests
