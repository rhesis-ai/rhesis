"""
Tests for GarakTagCatalog — the dynamic tag description loader.

These tests verify that the catalog can read garak's tags.misp.tsv and
expose tag descriptions and topic titles correctly.
"""

import pytest

from rhesis.backend.app.services.garak.tag_catalog import (
    GarakTagCatalog,
    get_tag_catalog,
)

# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCatalogLoading:
    """Verify the TSV loads without errors and contains expected entries."""

    def test_catalog_loads_without_error(self):
        catalog = GarakTagCatalog()
        assert catalog.size > 0

    def test_catalog_has_owasp_entries(self):
        catalog = GarakTagCatalog()
        for i in range(1, 11):
            key = f"owasp:llm{i:02d}"
            desc = catalog.get_description(key)
            assert desc is not None, f"Missing description for {key}"
            assert len(desc) > 0

    def test_catalog_has_avid_entries(self):
        catalog = GarakTagCatalog()
        desc = catalog.get_description("avid-effect:security:S0100")
        assert desc is not None

    def test_catalog_has_quality_entries(self):
        catalog = GarakTagCatalog()
        desc = catalog.get_description("quality:Behavioral:ContentSafety:Toxicity")
        assert desc is not None


# ---------------------------------------------------------------------------
# get_description
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetDescription:
    def test_owasp_llm01_contains_prompt_injection(self):
        catalog = GarakTagCatalog()
        desc = catalog.get_description("owasp:llm01")
        assert "Prompt Injection" in desc

    def test_description_combines_title_and_body(self):
        """The returned string should contain both the title and description."""
        catalog = GarakTagCatalog()
        desc = catalog.get_description("owasp:llm01")
        assert "\u2014" in desc  # em-dash separator

    def test_unknown_tag_returns_none(self):
        catalog = GarakTagCatalog()
        assert catalog.get_description("nonexistent:tag:xyz") is None


# ---------------------------------------------------------------------------
# get_topic
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetTopic:
    def test_owasp_tag_returns_title(self):
        catalog = GarakTagCatalog()
        topic = catalog.get_topic("owasp:llm01")
        assert topic is not None
        assert "LLM01" in topic

    def test_quality_tag_returns_title(self):
        catalog = GarakTagCatalog()
        topic = catalog.get_topic("quality:Behavioral:ContentSafety:Toxicity")
        assert topic is not None

    def test_payload_tag_uses_fallback(self):
        catalog = GarakTagCatalog()
        assert catalog.get_topic("payload:jailbreak") == "Jailbreak"
        assert catalog.get_topic("payload:unwanted") == "Unwanted Content"
        assert catalog.get_topic("payload:generic") == "Generic Attacks"

    def test_unknown_tag_returns_none(self):
        catalog = GarakTagCatalog()
        assert catalog.get_topic("nonexistent:tag:xyz") is None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSingleton:
    def test_get_tag_catalog_returns_same_instance(self):
        a = get_tag_catalog()
        b = get_tag_catalog()
        assert a is b

    def test_singleton_is_a_catalog(self):
        assert isinstance(get_tag_catalog(), GarakTagCatalog)
