"""Build Rhesis test data from a Garak probe.

Import and sync both create tests from probe prompts, so they share this builder
to keep the metadata the same.
"""

from typing import Any, List, Optional, Set

from rhesis.backend.app.schemas import test_set as test_set_schemas
from rhesis.backend.app.services.garak.probes import GarakProbeInfo
from rhesis.backend.app.services.garak.taxonomy import resolve_requirement
from rhesis.backend.app.utils.garak_nul_escape import encode_prompt_and_notes


def build_tests_data(
    probe: GarakProbeInfo,
    mapping: Any,  # GarakMapping
    probe_ids: Optional[Set[str]] = None,
) -> List[test_set_schemas.TestData]:
    """Build one test per non-empty probe prompt.

    Args:
        probe: The Garak probe to build tests from.
        mapping: Taxonomy mapping for the probe's module.
        probe_ids: If given, only prompts whose ``garak_probe_id`` is in this set.
    """
    requirement = resolve_requirement(probe.tags)
    tests_data = []

    for idx, prompt_content in enumerate(probe.prompts):
        probe_id = f"{probe.full_name}.{idx}"
        if probe_ids is not None and probe_id not in probe_ids:
            continue
        if not prompt_content or not prompt_content.strip():
            continue

        test_metadata = {
            "source": "garak",
            "garak_probe_id": probe_id,
            "garak_probe_class": probe.class_name,
            "garak_module": probe.module_name,
            "garak_tags": probe.tags,
        }

        # prompt_notes[i] holds the detector triggers for prompts[i] (e.g. for
        # AttackRogueString/DecodeMatch); the metric reads them at evaluation time.
        notes = None
        if probe.prompt_notes and idx < len(probe.prompt_notes) and probe.prompt_notes[idx]:
            notes = probe.prompt_notes[idx]

        prompt_content, notes = encode_prompt_and_notes(prompt_content, notes, test_metadata)
        if notes:
            test_metadata["garak_notes"] = notes

        tests_data.append(
            test_set_schemas.TestData(
                prompt=test_set_schemas.TestPrompt(
                    content=prompt_content,
                    language_code="en",
                ),
                requirement=requirement,
                category=mapping.category,
                topic=mapping.topic,
                test_type="Single-Turn",
                metadata=test_metadata,
            )
        )

    return tests_data
