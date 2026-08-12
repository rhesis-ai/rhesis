"""Regulatory knowledge base: schema, indexes, validation, and citation checks.

Structured lookup only — no vector store, no embedding model, no live regulatory API. Every
answer the agent gives has to resolve to a node loaded here, which is what makes the citations
checkable in Python rather than merely plausible.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, PrivateAttr


def _default_knowledge_dir() -> Path:
    """Where the YAML lives.

    Two locations, because the package is used both ways. A git checkout or an editable install
    finds `knowledge/` at the project root. An installed wheel finds the copy hatchling
    force-includes beside this module. Checking the project root first means a developer editing
    the YAML sees the change without reinstalling.
    """
    project_root = Path(__file__).resolve().parents[2] / "knowledge"
    if project_root.is_dir():
        return project_root
    return Path(__file__).resolve().parent / "_knowledge"


DEFAULT_KNOWLEDGE_DIR = _default_knowledge_dir()

# Jurisdiction-prefixed ids such as EU-MD-CLASS-011 or US-SW-CDS-3060. The two-letter prefix is
# what keeps ordinary uppercase prose (ISO-13485, MDR-2017) from reading as a citation.
NODE_ID_PATTERN = re.compile(r"\b[A-Z]{2}-[A-Z0-9]+(?:-[A-Z0-9]+)+\b")

DISCLAIMER = (
    "This is regulatory literacy information, not legal advice, and not a compliance "
    "determination. Verify every citation against the primary source before relying on it."
)


class KnowledgeBaseError(RuntimeError):
    """Raised when the loaded knowledge base fails validation."""


class Instrument(BaseModel):
    type: str
    citation: str
    binding: bool
    url: str


class NodeStatus(BaseModel):
    in_force: bool
    applicable_from: str
    transition_provisions: str = ""
    amended_by: list[str] = Field(default_factory=list)
    verified_on: str = ""


class RegulationNode(BaseModel):
    """One node of the D2 taxonomy, schema-complete."""

    id: str
    name: str
    parent_id: str
    jurisdiction: str
    product_families: list[str]
    lifecycle_phase: list[str]
    instrument: Instrument
    status: NodeStatus
    scope_trigger: str
    obligation_summary: str
    responsible_actor: list[str]
    evidence_artifacts: list[str]
    competent_authority: list[str]
    timing: str
    consequences_of_noncompliance: str
    related_nodes: list[str] = Field(default_factory=list)
    common_pitfalls: str = ""
    confidence: str = "medium"
    notes: str = ""


class DecisionBranch(BaseModel):
    id: str
    summary: str
    nodes: list[str] = Field(default_factory=list)
    eu_pathway: str = ""
    us_pathway: str = ""


class DecisionTree(BaseModel):
    id: str
    name: str
    question: str
    depends_on: list[str] = Field(default_factory=list)
    branches: list[DecisionBranch] = Field(default_factory=list)

    def branch(self, branch_id: str) -> DecisionBranch | None:
        return next((b for b in self.branches if b.id == branch_id), None)


class Comparison(BaseModel):
    concept: str
    eu: str
    us: str
    false_friend: str
    nodes: list[str] = Field(default_factory=list)


class Source(BaseModel):
    citation: str
    kind: str
    binding: bool
    status: str
    url: str


class Gap(BaseModel):
    id: str
    title: str
    confidence: str
    citation_unverified: bool = False
    node_ids: list[str] = Field(default_factory=list)
    summary: str
    action: str


class KnowledgeBase(BaseModel):
    """The five YAML files, parsed and indexed."""

    verified_on: str
    nodes: list[RegulationNode]
    trees: list[DecisionTree]
    comparisons: list[Comparison]
    sources: list[Source]
    gaps: list[Gap]

    _index: dict[str, RegulationNode] = PrivateAttr(default_factory=dict)

    def model_post_init(self, _context: Any) -> None:
        # Built once here rather than per lookup: validation and the briefing both hit it hard.
        # A duplicate id collapses in this dict, which is why validate_knowledge_base counts ids
        # from the list instead.
        self._index = {node.id: node for node in self.nodes}

    def lookup(self, node_id: str) -> RegulationNode | None:
        """Return the node with this id, or ``None``."""
        return self._index.get(node_id)

    def tree(self, tree_id: str) -> DecisionTree | None:
        """Return the decision tree with this id, or ``None``."""
        return next((t for t in self.trees if t.id == tree_id), None)

    def find_nodes(
        self,
        *,
        jurisdiction: str | None = None,
        family: str | None = None,
        phase: str | None = None,
    ) -> list[RegulationNode]:
        """Return nodes matching every filter given, in load order."""
        found = self.nodes
        if jurisdiction:
            found = [n for n in found if n.jurisdiction == jurisdiction]
        if family:
            found = [n for n in found if family in n.product_families]
        if phase:
            found = [n for n in found if phase in n.lifecycle_phase]
        return list(found)

    def search(self, query: str, *, limit: int = 10) -> list[RegulationNode]:
        """Keyword search over name, scope trigger and obligation summary."""
        terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 2]
        if not terms:
            return []
        scored: list[tuple[int, int, RegulationNode]] = []
        for position, node in enumerate(self.nodes):
            haystack = f"{node.name} {node.scope_trigger} {node.obligation_summary}".lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((-score, position, node))
        return [node for _, _, node in sorted(scored, key=lambda row: row[:2])][:limit]

    def verify_citations(self, text: str) -> list[str]:
        """Return every node id referenced in ``text`` that this knowledge base does not hold.

        The critic layer runs this before a model ever reads the draft, so an invented id is a
        mechanical rejection rather than a judgement call.
        """
        missing: list[str] = []
        for candidate in NODE_ID_PATTERN.findall(text):
            if candidate not in self._index and candidate not in missing:
                missing.append(candidate)
        return missing

    def staleness_warnings(self, node_ids: list[str]) -> list[str]:
        """Return the warning lines that must accompany the given nodes.

        Three triggers: low confidence, a citation the gap log marks unverified, and a live
        transition provision. Transition dates are the most volatile part of the taxonomy, so a
        node carrying one never travels without its warning.
        """
        warnings: list[str] = []
        for node_id in node_ids:
            node = self.lookup(node_id)
            if node is None:
                continue
            for gap in self.gaps:
                if node_id in gap.node_ids and gap.citation_unverified:
                    warnings.append(f"{node_id}: CITATION UNVERIFIED — {gap.summary} {gap.action}")
            if node.confidence == "low":
                warnings.append(
                    f"{node_id}: low confidence in this knowledge base. "
                    "Check the primary source before relying on it."
                )
            if node.status.transition_provisions:
                warnings.append(
                    f"{node_id}: live transition provision — "
                    f"{node.status.transition_provisions}. Transition deadlines change; "
                    "re-verify against the primary source."
                )
        return warnings

    def gaps_for(self, node_ids: list[str]) -> list[Gap]:
        """Return gap-log entries touching any of these nodes."""
        wanted = set(node_ids)
        return [gap for gap in self.gaps if wanted.intersection(gap.node_ids)]

    def comparisons_for(self, node_ids: list[str]) -> list[Comparison]:
        """Return EU/US comparison rows touching any of these nodes."""
        wanted = set(node_ids)
        return [row for row in self.comparisons if wanted.intersection(row.nodes)]


def _read(directory: Path, filename: str) -> dict[str, Any]:
    path = directory / filename
    if not path.is_file():
        raise KnowledgeBaseError(f"Knowledge base file missing: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise KnowledgeBaseError(f"Knowledge base file is not a mapping: {path}")
    return loaded


def load_knowledge_base(directory: Path | None = None) -> KnowledgeBase:
    """Parse the five YAML files. Raises :class:`KnowledgeBaseError` on a malformed file."""
    source_dir = directory or DEFAULT_KNOWLEDGE_DIR
    taxonomy = _read(source_dir, "taxonomy.yaml")
    try:
        return KnowledgeBase(
            verified_on=str(taxonomy.get("verified_on", "")),
            nodes=taxonomy.get("nodes") or [],
            trees=_read(source_dir, "decision_trees.yaml").get("trees") or [],
            comparisons=_read(source_dir, "comparison.yaml").get("comparisons") or [],
            sources=_read(source_dir, "sources.yaml").get("sources") or [],
            gaps=_read(source_dir, "gaps.yaml").get("gaps") or [],
        )
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        raise KnowledgeBaseError(f"Knowledge base failed schema validation: {exc}") from exc


def validate_knowledge_base(base: KnowledgeBase | None = None) -> KnowledgeBase:
    """Check the knowledge base and raise on any problem.

    Called from the app's startup hook so a broken base stops the server starting. A dangling
    citation that only shows up mid-conversation is far worse than a failed boot.
    """
    checked = base or get_knowledge_base()
    problems: list[str] = []

    seen: set[str] = set()
    for node in checked.nodes:
        if node.id in seen:
            problems.append(f"duplicate node id: {node.id}")
        seen.add(node.id)
        if not node.status.verified_on:
            problems.append(f"{node.id}: missing status.verified_on")

    for node in checked.nodes:
        for related in node.related_nodes:
            if related not in seen:
                problems.append(f"{node.id}: related_nodes points at unknown id {related}")

    for tree in checked.trees:
        for branch in tree.branches:
            for node_id in branch.nodes:
                if node_id not in seen:
                    problems.append(
                        f"{tree.id}/{branch.id}: terminal points at unknown id {node_id}"
                    )

    for row in checked.comparisons:
        for node_id in row.nodes:
            if node_id not in seen:
                problems.append(f"comparison {row.concept!r}: unknown id {node_id}")

    for gap in checked.gaps:
        for node_id in gap.node_ids:
            if node_id not in seen:
                problems.append(f"gap {gap.id}: unknown id {node_id}")

    if problems:
        joined = "; ".join(problems)
        raise KnowledgeBaseError(
            f"Knowledge base failed validation ({len(problems)} problems): {joined}"
        )
    return checked


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    """Return the process-wide knowledge base, parsing the YAML files on first use."""
    return load_knowledge_base()


__all__ = [
    "DEFAULT_KNOWLEDGE_DIR",
    "DISCLAIMER",
    "Comparison",
    "DecisionBranch",
    "DecisionTree",
    "Gap",
    "Instrument",
    "KnowledgeBase",
    "KnowledgeBaseError",
    "NODE_ID_PATTERN",
    "NodeStatus",
    "RegulationNode",
    "Source",
    "get_knowledge_base",
    "load_knowledge_base",
    "validate_knowledge_base",
]
