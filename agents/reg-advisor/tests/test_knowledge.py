"""Knowledge base loading, validation, and citation checks."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from reg_advisor.knowledge import (
    DEFAULT_KNOWLEDGE_DIR,
    KnowledgeBase,
    KnowledgeBaseError,
    get_knowledge_base,
    load_knowledge_base,
    validate_knowledge_base,
)


@pytest.fixture
def base() -> KnowledgeBase:
    return get_knowledge_base()


@pytest.fixture
def knowledge_copy(tmp_path: Path) -> Path:
    """A writable copy of the real knowledge base, for breaking on purpose."""
    target = tmp_path / "knowledge"
    shutil.copytree(DEFAULT_KNOWLEDGE_DIR, target)
    return target


def _edit_yaml(path: Path, mutate) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


# --- loading and schema -----------------------------------------------------------------


def test_shipped_knowledge_base_validates(base: KnowledgeBase) -> None:
    assert validate_knowledge_base(base) is base
    assert base.verified_on == "2026-08-11"
    assert base.nodes and base.trees and base.comparisons and base.sources and base.gaps


def test_every_node_is_schema_complete(base: KnowledgeBase) -> None:
    for node in base.nodes:
        assert node.jurisdiction in {"EU", "US"}, node.id
        assert node.product_families and node.lifecycle_phase, node.id
        assert node.instrument.citation and node.instrument.url, node.id
        assert node.obligation_summary and node.scope_trigger, node.id
        assert node.confidence in {"low", "medium", "high"}, node.id


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(KnowledgeBaseError, match="missing"):
        load_knowledge_base(tmp_path)


def test_malformed_node_raises(knowledge_copy: Path) -> None:
    _edit_yaml(
        knowledge_copy / "taxonomy.yaml",
        lambda data: data["nodes"][0].pop("obligation_summary"),
    )
    with pytest.raises(KnowledgeBaseError, match="schema validation"):
        load_knowledge_base(knowledge_copy)


# --- indexes and lookup -----------------------------------------------------------------


def test_lookup_and_find_nodes(base: KnowledgeBase) -> None:
    rule_11 = base.lookup("EU-MD-CLASS-011")
    assert rule_11 is not None
    assert rule_11.jurisdiction == "EU"
    assert base.lookup("EU-MD-NOPE-000") is None

    eu_post_market = base.find_nodes(jurisdiction="EU", phase="post_market")
    assert {node.id for node in eu_post_market} >= {"EU-MD-PMS-084", "EU-MD-VIG-087"}
    assert all(node.jurisdiction == "EU" for node in eu_post_market)

    saas = base.find_nodes(family="SaMD")
    assert "EU-MD-CLASS-011" in {node.id for node in saas}


def test_search_ranks_by_term_frequency(base: KnowledgeBase) -> None:
    hits = base.search("companion diagnostic")
    assert {"EU-IVD-CLASS-R3F", "US-IVD-CDX-PMA"} <= {node.id for node in hits}
    assert base.search("of") == []


def test_tree_and_branch_lookup(base: KnowledgeBase) -> None:
    tree = base.tree("ai_act_stack")
    assert tree is not None
    branch = tree.branch("ai_high_risk")
    assert branch is not None
    assert "EU-AI-HIGHRISK-006" in branch.nodes
    assert tree.branch("no_such_branch") is None


# --- validation failures ----------------------------------------------------------------


def test_dangling_related_node_fails_validation(knowledge_copy: Path) -> None:
    _edit_yaml(
        knowledge_copy / "taxonomy.yaml",
        lambda data: data["nodes"][0]["related_nodes"].append("EU-MD-GHOST-404"),
    )
    with pytest.raises(KnowledgeBaseError, match="EU-MD-GHOST-404"):
        validate_knowledge_base(load_knowledge_base(knowledge_copy))


def test_dangling_decision_tree_terminal_fails_validation(knowledge_copy: Path) -> None:
    _edit_yaml(
        knowledge_copy / "decision_trees.yaml",
        lambda data: data["trees"][0]["branches"][0]["nodes"].append("US-XX-GHOST-001"),
    )
    with pytest.raises(KnowledgeBaseError, match="terminal points at unknown id"):
        validate_knowledge_base(load_knowledge_base(knowledge_copy))


def test_duplicate_node_id_fails_validation(knowledge_copy: Path) -> None:
    _edit_yaml(
        knowledge_copy / "taxonomy.yaml",
        lambda data: data["nodes"].append(dict(data["nodes"][0])),
    )
    with pytest.raises(KnowledgeBaseError, match="duplicate node id"):
        validate_knowledge_base(load_knowledge_base(knowledge_copy))


def test_missing_verified_on_fails_validation(knowledge_copy: Path) -> None:
    def blank_it(data: dict) -> None:
        data["nodes"][0]["status"]["verified_on"] = ""

    _edit_yaml(knowledge_copy / "taxonomy.yaml", blank_it)
    with pytest.raises(KnowledgeBaseError, match="missing status.verified_on"):
        validate_knowledge_base(load_knowledge_base(knowledge_copy))


# --- citation integrity -----------------------------------------------------------------


def test_verify_citations_catches_an_invented_id(base: KnowledgeBase) -> None:
    text = "Under EU-MD-CLASS-011 this is Class IIa, and EU-MD-RULE-042 confirms it."
    assert base.verify_citations(text) == ["EU-MD-RULE-042"]


def test_verify_citations_ignores_ordinary_prose(base: KnowledgeBase) -> None:
    text = "See ISO-13485 and the MDR. Class IIa applies. Contact the EU or US authority."
    assert base.verify_citations(text) == []


def test_verify_citations_reports_each_missing_id_once(base: KnowledgeBase) -> None:
    text = "EU-MD-GHOST-001 and EU-MD-GHOST-001 again, plus US-MD-GHOST-002."
    assert base.verify_citations(text) == ["EU-MD-GHOST-001", "US-MD-GHOST-002"]


# --- staleness --------------------------------------------------------------------------


def test_staleness_warning_fires_on_a_transition_provision(base: KnowledgeBase) -> None:
    warnings = base.staleness_warnings(["EU-MD-TRANS-120"])
    assert any("live transition provision" in line for line in warnings)
    assert all(line.startswith("EU-MD-TRANS-120:") for line in warnings)


def test_staleness_warning_fires_on_low_confidence(base: KnowledgeBase) -> None:
    assert base.lookup("EU-IVD-TRANS-110").confidence == "low"
    warnings = base.staleness_warnings(["EU-IVD-TRANS-110"])
    assert any("low confidence" in line for line in warnings)


def test_staleness_warning_fires_on_an_unverified_citation(base: KnowledgeBase) -> None:
    warnings = base.staleness_warnings(["EU-AI-HIGHRISK-006"])
    assert any("CITATION UNVERIFIED" in line for line in warnings)


def test_staleness_is_quiet_for_a_settled_node(base: KnowledgeBase) -> None:
    assert base.staleness_warnings(["US-MD-PATH-510K"]) == []


def test_staleness_ignores_unknown_ids(base: KnowledgeBase) -> None:
    assert base.staleness_warnings(["EU-MD-GHOST-001"]) == []


# --- cross-references -------------------------------------------------------------------


def test_gaps_and_comparisons_for_a_node(base: KnowledgeBase) -> None:
    gap_ids = {gap.id for gap in base.gaps_for(["EU-AI-HIGHRISK-006"])}
    assert "ai-act-digital-omnibus" in gap_ids

    concepts = {row.concept for row in base.comparisons_for(["EU-MD-CLASS-011"])}
    assert "Clinical decision support software" in concepts
