"""OWASP Top 10 adversarial synthesizer.

Downloads any OWASP Top 10 report PDF (LLM, Agentic, etc.) via
:func:`~rhesis.sdk.services.owasp_extractor.fetch_owasp_sections`, and generates
red-team test cases for each risk section driven entirely by the official report
content — no hardcoded category descriptions.

Works with any OWASP Top 10 report that follows the standard one-section-per-page
PDF layout (LLM Top 10, Agentic Top 10, etc.).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Collection, Dict, List, Optional, Union

from jinja2 import Template
from pydantic import BaseModel, Field

from rhesis.sdk.entities.test_set import TestSet
from rhesis.sdk.enums import TestType
from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.owasp_extractor import (
    DEFAULT_OWASP_AGENTIC_PDF_URL,
    DEFAULT_OWASP_LLM_PDF_URL,
    DEFAULT_SUBSECTION_EXCLUSIONS,
    ReportSection,
    fetch_owasp_sections,
)
from rhesis.sdk.synthesizers.base import TestSetSynthesizer
from rhesis.sdk.synthesizers.utils import load_prompt_template

logger = logging.getLogger(__name__)


# Flat schema for multi-turn generation, repacked to the nested test_configuration
# shape after generation — mirrors multi_turn.base.FlatTest.
class FlatMultiTurnTest(BaseModel):
    test_configuration_goal: str
    test_configuration_instructions: str
    test_configuration_restrictions: str
    test_configuration_scenario: str
    test_configuration_min_turns: int = Field(ge=1, le=50)
    test_configuration_max_turns: int = Field(ge=1, le=50)
    behavior: str
    category: str
    topic: str


class FlatMultiTurnTests(BaseModel):
    tests: List[FlatMultiTurnTest]


__all__ = [
    "OWASPSynthesizer",
    "DEFAULT_OWASP_LLM_PDF_URL",
    "DEFAULT_OWASP_AGENTIC_PDF_URL",
    "DEFAULT_SUBSECTION_EXCLUSIONS",
    "ReportSection",
]


class OWASPSynthesizer(TestSetSynthesizer):
    """Generates adversarial test cases for any OWASP Top 10 report.

    Downloads the specified OWASP PDF, extracts its text, splits it into
    per-risk sections, and generates LLM-tailored attack prompts for each
    section.  The official report text is the sole generation context —
    no hardcoded category descriptions or attack instructions.

    Works with any OWASP Top 10 report (LLM, Agentic, …) that uses the
    standard one-section-per-page PDF layout.

    Usage::

        # LLM Top 10 (default URL)
        synthesizer = OWASPSynthesizer(
            purpose="Customer service chatbot for a bank with access to account data",
        )
        test_set = synthesizer.generate(num_tests=30)  # 3 per section

        # Agentic Top 10
        from rhesis.sdk.services.owasp_extractor import DEFAULT_OWASP_AGENTIC_PDF_URL
        synthesizer = OWASPSynthesizer(
            purpose="Autonomous coding agent with shell access",
            report_url=DEFAULT_OWASP_AGENTIC_PDF_URL,
        )

        # Custom report URL, specific sections only
        synthesizer = OWASPSynthesizer(
            purpose="...",
            report_url="https://example.com/custom-top10.pdf",
            categories=["llm01", "llm07"],
        )
    """

    prompt_template_file = "owasp_synthesizer.jinja"
    multi_turn_prompt_template_file = "owasp_synthesizer_multi_turn.jinja"

    def __init__(
        self,
        purpose: str,
        report_url: str = DEFAULT_OWASP_LLM_PDF_URL,
        categories: Optional[List[str]] = None,
        subsection_exclusions: Collection[str] = DEFAULT_SUBSECTION_EXCLUSIONS,
        batch_size: int = 10,
        model: Optional[Union[str, BaseLLM]] = None,
        behavior: str = "OWASP LLM Top 10",
        test_type: Union[str, TestType] = TestType.SINGLE_TURN,
        cache_key: Optional[str] = None,
        cache_loader: Optional[Callable[[str], Optional[List[dict]]]] = None,
        cache_writer: Optional[Callable[[str, List[dict]], None]] = None,
    ):
        """
        Args:
            purpose: What the system under test does, e.g. "customer service
                chatbot for a bank".  The generator LLM uses this to tailor
                each attack to the specific system.
            report_url: Direct URL to an OWASP Top 10 PDF.
                Defaults to the LLM Top 10 v2025.
            categories: Optional list of section IDs to include, e.g.
                ``["llm01", "llm07"]`` or ``["asi01", "asi03"]``.
                Defaults to all sections found in the report.
            subsection_exclusions: Subsection headings to strip from every
                section before generation.  Defaults to
                :data:`~rhesis.sdk.services.owasp_extractor.DEFAULT_SUBSECTION_EXCLUSIONS`
                which drops reference appendices.  Pass an empty collection to
                keep all subsections.
            batch_size: Max attacks to generate per LLM call per section.
            model: LLM to use for generation.
            behavior: Behavior label stored on every generated test, used for
                analytics grouping.  Override to e.g. ``"OWASP Agentic Top 10"``
                when using :data:`DEFAULT_OWASP_AGENTIC_PDF_URL`.
            test_type: ``SINGLE_TURN`` (default) generates one-shot prompts;
                ``MULTI_TURN`` generates conversational attacks.
            cache_key, cache_loader, cache_writer: Optional content-cache hooks
                passed through to
                :func:`~rhesis.sdk.services.owasp_extractor.fetch_owasp_sections`.
        """
        super().__init__(batch_size=batch_size, model=model, harmful=True)
        self.purpose = purpose
        self._report_url = report_url
        self._behavior = behavior
        self._category_filter = [c.lower() for c in categories] if categories else None
        self._subsection_exclusions = subsection_exclusions
        self._cache_key = cache_key
        self._cache_loader = cache_loader
        self._cache_writer = cache_writer
        self._sections: Optional[List[ReportSection]] = None  # lazy-loaded on first use
        self.test_type = test_type if isinstance(test_type, TestType) else TestType(test_type)
        self._multi_turn_template: Optional[Template] = None  # lazy-loaded on first use

    # ------------------------------------------------------------------
    # TestSetSynthesizer interface
    # ------------------------------------------------------------------

    def _get_template_context(self, **generate_kwargs: Any) -> Dict[str, Any]:
        # Required by the abstract base; the real per-section context is built
        # in _build_section_context, called from the overridden
        # _generate_without_sources.
        sections = self._get_sections()
        if not sections:
            raise ValueError("No sections found in the OWASP report.")
        return self._build_section_context(sections[0], **generate_kwargs)

    @property
    def report_url(self) -> str:
        return self._report_url

    def _get_synthesizer_name(self) -> str:
        return "OWASPSynthesizer"

    def generate(self, num_tests: int = 10, **kwargs: Any) -> TestSet:
        """Generate the test set, then stamp multi-turn metadata (the base class
        always sets test_set_type=SINGLE_TURN), mirroring MultiTurnSynthesizer.generate."""
        test_set = super().generate(num_tests=num_tests, **kwargs)
        if self.test_type == TestType.MULTI_TURN:
            test_set.test_set_type = TestType.MULTI_TURN
            if test_set.name:
                test_set.name = f"{test_set.name} (Multi-Turn)"
        return test_set

    # ------------------------------------------------------------------
    # Core generation — one pass per section
    # ------------------------------------------------------------------

    def _generate_without_sources(self, num_tests: int = 10, **kwargs: Any) -> List[Dict[str, Any]]:
        """Distribute *num_tests* across all selected sections and generate."""
        sections = self._get_sections()
        if not sections:
            raise ValueError("No sections found in the OWASP report.")

        counts = self._distribute(num_tests, len(sections))
        all_tests: List[Dict[str, Any]] = []

        for section, n in zip(sections, counts):
            if n == 0:
                continue
            logger.info(
                "[OWASPSynthesizer] Generating %d tests for %s — %s",
                n,
                section.id.upper(),
                section.name,
            )
            context = self._build_section_context(section, **kwargs)
            if self.test_type == TestType.MULTI_TURN:
                tests = self._generate_multiturn_tests(n, context)
            else:
                tests = self._generate_with_retry(n, **context)
            for t in tests:
                t.setdefault("metadata", {})["owasp_category"] = section.id
                t.setdefault("metadata", {})["owasp_name"] = section.name
            all_tests.extend(tests)
            logger.info(
                "[OWASPSynthesizer] %s: got %d/%d tests",
                section.id.upper(),
                len(tests),
                n,
            )

        return all_tests

    # Multi-turn generation — modeled on MultiTurnSynthesizer._generate_batch.

    def _get_multi_turn_template(self) -> Template:
        """Lazily load the multi-turn OWASP Jinja template."""
        if self._multi_turn_template is None:
            self._multi_turn_template = load_prompt_template(self.multi_turn_prompt_template_file)
        return self._multi_turn_template

    @staticmethod
    def _flat_multiturn_test_to_nested(flat: Dict[str, Any]) -> Dict[str, Any]:
        """Repack a flat multi-turn test dict (LLM output) into the nested shape."""
        return {
            "test_configuration": {
                "goal": flat["test_configuration_goal"],
                "instructions": flat["test_configuration_instructions"],
                "restrictions": flat["test_configuration_restrictions"],
                "scenario": flat["test_configuration_scenario"],
                "min_turns": int(flat["test_configuration_min_turns"]),
                "max_turns": int(flat["test_configuration_max_turns"]),
            },
            "behavior": flat["behavior"],
            "category": flat["category"],
            "topic": flat["topic"],
        }

    def _generate_multiturn_tests(
        self, num_tests: int, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate multi-turn OWASP tests for one section, batching by ``self.batch_size``."""
        template = self._get_multi_turn_template()
        all_tests: List[Dict[str, Any]] = []
        remaining = num_tests

        while remaining > 0:
            batch_n = min(remaining, self.batch_size)
            prompt = template.render(num_tests=batch_n, **context)

            try:
                response = self.model.generate(prompt=prompt, schema=FlatMultiTurnTests)
            except Exception:
                logger.exception("[OWASPSynthesizer] Multi-turn batch generation failed")
                break

            if not isinstance(response, dict) or "tests" not in response:
                logger.error(
                    "[OWASPSynthesizer] Multi-turn batch: unexpected response type=%s: %s",
                    type(response).__name__,
                    str(response)[:500],
                )
                break

            flat_tests = response["tests"][:batch_n]
            if not flat_tests:
                logger.warning("[OWASPSynthesizer] Multi-turn batch returned no tests")
                break

            for flat in flat_tests:
                all_tests.append(
                    {
                        **self._flat_multiturn_test_to_nested(flat),
                        "test_type": TestType.MULTI_TURN.value,
                    }
                )
            remaining -= len(flat_tests)

        return all_tests

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_sections(self) -> List[ReportSection]:
        """Fetch and parse the OWASP PDF on first call; return cached result."""
        if self._sections is not None:
            return self._sections

        all_sections = fetch_owasp_sections(
            self._report_url,
            subsection_exclusions=self._subsection_exclusions,
            cache_key=self._cache_key,
            cache_loader=self._cache_loader,
            cache_writer=self._cache_writer,
        )

        if self._category_filter is not None:
            valid_ids = {s.id for s in all_sections}
            unknown = [c for c in self._category_filter if c not in valid_ids]
            if unknown:
                raise ValueError(
                    f"Unknown categories: {unknown}. Sections found in report: {sorted(valid_ids)}"
                )
            self._sections = [s for s in all_sections if s.id in self._category_filter]
        else:
            self._sections = all_sections

        logger.info(
            "[OWASPSynthesizer] Loaded %d sections: %s",
            len(self._sections),
            [s.id for s in self._sections],
        )
        return self._sections

    def _build_section_context(self, section: ReportSection, **extra: Any) -> Dict[str, Any]:
        """Build the Jinja template context for one OWASP section."""
        return {
            "purpose": self.purpose,
            "section_id": section.id,
            "section_name": section.name,
            "section_content": section.content,
            "behavior": self._behavior,
            "topic": section.name.lower(),
            "harmful": True,
            **extra,
        }

    @staticmethod
    def _distribute(total: int, n: int) -> List[int]:
        """Spread *total* as evenly as possible across *n* buckets."""
        if n == 0:
            return []
        base, remainder = divmod(total, n)
        return [base + (1 if i < remainder else 0) for i in range(n)]
