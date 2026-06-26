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
from typing import Any, Collection, Dict, List, Optional, Union

from rhesis.sdk.models.base import BaseLLM
from rhesis.sdk.services.owasp_extractor import (
    DEFAULT_OWASP_AGENTIC_PDF_URL,
    DEFAULT_OWASP_LLM_PDF_URL,
    DEFAULT_SUBSECTION_BLACKLIST,
    ReportSection,
    fetch_owasp_sections,
)
from rhesis.sdk.synthesizers.base import TestSetSynthesizer

logger = logging.getLogger(__name__)

__all__ = [
    "OWASPSynthesizer",
    "DEFAULT_OWASP_LLM_PDF_URL",
    "DEFAULT_OWASP_AGENTIC_PDF_URL",
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

    def __init__(
        self,
        purpose: str,
        report_url: str = DEFAULT_OWASP_LLM_PDF_URL,
        categories: Optional[List[str]] = None,
        subsection_blacklist: Collection[str] = DEFAULT_SUBSECTION_BLACKLIST,
        batch_size: int = 10,
        model: Optional[Union[str, BaseLLM]] = None,
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
            subsection_blacklist: Subsection headings to strip from every
                section before generation.  Defaults to
                :data:`~rhesis.sdk.services.owasp_extractor.DEFAULT_SUBSECTION_BLACKLIST`
                which drops reference appendices.  Pass an empty collection to
                keep all subsections.
            batch_size: Max attacks to generate per LLM call per section.
            model: LLM to use for generation.
        """
        super().__init__(batch_size=batch_size, model=model, harmful=True)
        self.purpose = purpose
        self._report_url = report_url
        self._category_filter = [c.lower() for c in categories] if categories else None
        self._subsection_blacklist = subsection_blacklist
        self._sections: Optional[List[ReportSection]] = None  # lazy-loaded on first use

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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_sections(self) -> List[ReportSection]:
        """Fetch and parse the OWASP PDF on first call; return cached result."""
        if self._sections is not None:
            return self._sections

        all_sections = fetch_owasp_sections(
            self._report_url, subsection_blacklist=self._subsection_blacklist
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
            "behavior": "Robustness",
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
