"""
Domain probing exploration strategy.

Discovers the target's purpose, core domain, terminology, persona,
and topic coverage through structured decomposition and conversational
probing.

Research influences:
    - ACD (Lu et al., ICLR 2025): open-ended task proposal via a
      scientist model; difficulty adaptation through self-reflection.
    - AutoRedTeamer (Zhou et al., NeurIPS 2025): risk decomposition —
      breaking a high-level category into testable components before
      generating probes.
"""

from typing import Any, Dict, List, Optional

from rhesis.penelope.strategies.base import ExplorationStrategy, register_strategy


class DomainProbingStrategy(ExplorationStrategy):
    """Probe the target to understand its domain and purpose.

    Decomposes domain discovery into five testable dimensions
    (inspired by AutoRedTeamer's risk decomposition), then probes
    each with difficulty calibration (inspired by ACD's
    self-reflection). Typically run first in a comprehensive sequence.
    """

    strategy_name = "domain_probing"
    strategy_description = (
        "Discover the target's purpose, core domain, terminology, "
        "and persona through structured decomposition and "
        "conversational probing."
    )
    strategy_max_turns = 5

    findings_fields = {
        "domain": "",
        "purpose": "",
        "persona": "",
        "key_topics": [],
        "terminology": [],
        "depth_assessment": "",
        "adjacent_domains": [],
    }

    dimensions = [
        (
            "scope",
            "Open with a broad question about what the target does. "
            "Let it introduce itself. From the response, identify the "
            "main topic areas and note which ones it volunteers vs. "
            "which you have to ask about.",
        ),
        (
            "depth",
            "For the most prominent topic area, ask a follow-up that "
            "requires specific, detailed knowledge. Compare the quality "
            "of this response to the introductory one. A detailed, "
            "accurate answer signals deep coverage; a vague or generic "
            "answer signals shallow coverage.",
        ),
        (
            "persona",
            "Pay attention to tone, formality, vocabulary, and whether "
            "it uses first person across your conversation. Note if it "
            "has a name, character, or consistent voice. You don't need "
            "a dedicated turn for this — observe it throughout.",
        ),
        (
            "terminology",
            "Record domain-specific terms, product names, or jargon "
            "the target uses consistently. Ask a question using general "
            "language and see if the target introduces specialized "
            "vocabulary in its response.",
        ),
        (
            "adjacent_domains",
            "Test topics one step outside the apparent core domain. "
            "If it covers travel, ask about travel insurance or visa "
            "requirements. This reveals where the domain boundary "
            "begins and which adjacent areas it partially handles.",
        ),
    ]

    def _goal_parts(
        self,
        target_name: str,
        target_description: str,
        previous_findings: Optional[Dict[str, Any]],
    ) -> List[str]:
        parts = [
            f"Discover the core domain, purpose, and personality of '{target_name}'.",
            "Determine what topics it covers, what terminology it uses, "
            "and how it presents itself (tone, persona, formality).",
        ]
        if target_description:
            parts.append(
                f"The target is described as: {target_description}. "
                "Verify whether this matches its actual behavior."
            )
        return parts

    def _opening(self, target_name: str, target_description: str) -> str:
        return (
            f"You are probing '{target_name}' to understand its domain "
            "and purpose. Your goal is to produce a structured domain "
            "map, not just a general impression."
        )

    def _body(
        self,
        target_name: str,
        target_description: str,
        previous_findings: Optional[Dict[str, Any]],
        **context: Any,
    ) -> List[str]:
        return [
            "## Decomposition — five dimensions to probe",
            "",
            "Before diving into conversation, understand the five "
            "dimensions you need to cover. Allocate your turns across "
            "them:",
            "",
            *self._render_dimensions(previous_findings),
        ]


register_strategy(DomainProbingStrategy())
