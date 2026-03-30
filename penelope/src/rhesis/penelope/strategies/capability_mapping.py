"""
Capability mapping exploration strategy.

Systematically maps the target's functional capabilities, interaction
patterns, supported features, and limitations by testing different
query types with progressive difficulty escalation.

Research influences:
    - ACD (Lu et al., ICLR 2025): open-ended task families across
      capability dimensions; difficulty adaptation; novelty filtering
      to avoid re-probing known areas.
    - HELM (Liang et al., 2022): capability taxonomy — factual,
      reasoning, multi-step, creative — applied conversationally.
"""

from typing import Any, Dict, List, Optional

from rhesis.penelope.strategies.base import ExplorationStrategy, register_strategy


class CapabilityMappingStrategy(ExplorationStrategy):
    """Systematically enumerate what the target can do.

    Tests across a query-type taxonomy (inspired by HELM's capability
    dimensions), with novelty-aware instructions that skip areas already
    characterized and difficulty escalation that finds where each
    capability degrades (inspired by ACD's self-reflection).
    """

    strategy_name = "capability_mapping"
    strategy_description = (
        "Systematically map the target's functional capabilities "
        "across query types (factual, procedural, analytical, "
        "multi-turn, edge-case) with progressive difficulty."
    )
    strategy_max_turns = 7

    findings_fields = {
        "capabilities": [],
        "limitations": [],
        "capability_ceilings": {},
        "interaction_patterns": "",
        "multi_turn_support": "",
        "query_type_coverage": {},
    }

    dimensions = [
        (
            "factual",
            "Straightforward questions requiring domain knowledge.",
        ),
        (
            "procedural",
            "Step-by-step walkthroughs or how-to instructions.",
        ),
        (
            "analytical",
            "Comparisons, trade-offs, or recommendations.",
        ),
        (
            "multi_turn",
            "Follow-ups that require remembering prior context.",
        ),
        (
            "edge_case",
            "Unusual inputs, ambiguous requests, boundary scenarios.",
        ),
    ]

    def _dimension_note(
        self, key: str, previous_findings: Optional[Dict[str, Any]]
    ) -> str:
        if not previous_findings:
            return ""
        caps = previous_findings.get("capabilities")
        if not isinstance(caps, list) or not caps:
            return ""

        cap_keys = {str(c).lower() for c in caps}

        if key == "factual" and "factual" in cap_keys:
            return (
                " Factual recall is already confirmed — go straight to "
                "a harder factual question to find where accuracy drops."
            )
        if key == "multi_turn" and ("multi_turn" in cap_keys or "multi-turn" in cap_keys):
            return (
                " Basic context retention is already confirmed — test "
                "a complex reference (e.g. referencing something from "
                "two turns ago, or combining information across turns)."
            )
        return ""

    def _goal_parts(
        self,
        target_name: str,
        target_description: str,
        previous_findings: Optional[Dict[str, Any]],
    ) -> List[str]:
        parts = [
            f"Enumerate the functional capabilities of '{target_name}'.",
            "Test five query types — factual, procedural, analytical, "
            "multi-turn, and edge-case — and for each, find the difficulty "
            "level where the target's competence degrades.",
        ]
        if previous_findings and previous_findings.get("domain"):
            parts.append(
                f"The target's domain is: {previous_findings['domain']}. "
                "Focus on capabilities within and adjacent to this domain."
            )
        elif target_description:
            parts.append(f"The target is described as: {target_description}.")
        return parts

    def _opening(self, target_name: str, target_description: str) -> str:
        return (
            f"You are mapping the capabilities of '{target_name}' by "
            "testing it across five query types with escalating difficulty."
        )

    def _body(
        self,
        target_name: str,
        target_description: str,
        previous_findings: Optional[Dict[str, Any]],
        **context: Any,
    ) -> List[str]:
        return [
            "## Query-type taxonomy",
            "",
            "Test each type at least once. Within each type, start with a "
            "moderate question and escalate:",
            "",
            *self._render_dimensions(previous_findings),
            "## Progressive difficulty escalation",
            "",
            "For each query type, follow this pattern:",
            "",
            "1. **Baseline probe** — a moderate-difficulty question the "
            "target should handle if it has the capability.",
            "2. **Stress test** — if the baseline succeeds, immediately "
            "ask a harder variant. Increase complexity, add ambiguity, "
            "or combine with another capability. Find the point where "
            "the target's response quality degrades.",
            "3. **Record the ceiling** — the hardest question the target "
            "handled well is its capability ceiling for that query type. "
            "This is more useful than just knowing it 'can' do something.",
        ]


register_strategy(CapabilityMappingStrategy())
