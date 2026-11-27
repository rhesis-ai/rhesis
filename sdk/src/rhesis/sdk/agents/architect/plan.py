"""ArchitectPlan and spec models for test suite configuration."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from rhesis.sdk.agents.constants import InternalTool, ToolMeta
from rhesis.sdk.metrics.targets import TARGETS, TargetKind

ReuseStatus = Literal["reuse", "improve", "new"]

_TARGET_CHOICES = "; ".join(
    f'"{kind.value}" ({preset.label}): {preset.description}' for kind, preset in TARGETS.items()
)

# Fields that track execution progress and must never be written by the LLM.
# Referenced by _strip_internal_fields (JSON schema builder) and by
# agent._strip_llm_internal_fields (runtime, on every save_plan).
_INTERNAL_FIELDS: frozenset = frozenset({"completed", "linked_metrics", "actual_tests"})


class ProjectSpec(BaseModel):
    """Specification for a Rhesis project."""

    name: str = Field(description="Project name")
    description: str = Field(description="Project description")
    completed: bool = Field(default=False, description="Whether this project has been created")


class RequirementSpec(BaseModel):
    """Specification for a requirement in the plan."""

    name: str = Field(description="Requirement name")
    description: str = Field(default="", description="What this requirement expects")
    reuse_status: ReuseStatus = Field(
        default="new",
        description="Whether to reuse an existing requirement, or create a new one",
    )
    existing_id: Optional[str] = Field(
        default=None,
        description="ID of the existing requirement when reuse_status is 'reuse'",
    )
    completed: bool = Field(
        default=False, description="Whether this item has been created/resolved"
    )


class TestSetSpec(BaseModel):
    """Specification for a test set within a project."""

    name: str = Field(description="Test set name")
    description: str = Field(description="Detailed test set description")
    short_description: str = Field(default="", description="Brief one-line summary")
    num_tests: int = Field(default=15, description="Number of tests to generate")
    test_type: Literal["Single-Turn", "Multi-Turn"] = Field(
        default="Single-Turn",
        description=(
            'Must be exactly "Single-Turn" or "Multi-Turn". Decide from '
            "what the user asked for and what the requirement needs: "
            "Multi-Turn when the test depends on earlier turns (context "
            "retention, multi-step tasks, tone under pressure, guardrails "
            "under repeated pressure); Single-Turn when a single prompt "
            "settles it. If the user asked for Multi-Turn tests, set this "
            "to Multi-Turn — it does not default to it."
        ),
    )
    generation_prompt: str = Field(
        default="",
        description="Prompt for test generation",
    )
    requirements: List[str] = Field(
        default_factory=list,
        description="Requirement names this test set targets",
    )
    categories: List[str] = Field(
        default_factory=list,
        description="Category tags for this test set",
    )
    topics: List[str] = Field(
        default_factory=list,
        description="Topic tags for this test set",
    )
    completed: bool = Field(default=False, description="Whether this test set has been generated")
    actual_tests: Optional[int] = Field(
        default=None,
        description=(
            "How many tests were actually written, counted from what the "
            "writes returned (internal progress tracker)"
        ),
    )

    def shortfall(self) -> Optional[int]:
        """How many planned tests are missing, or None if nothing is missing.

        Only a set that came up short is worth flagging. An overshoot is
        someone adding tests on purpose, and an unwritten set (``None``) has
        not been attempted yet.
        """
        if self.actual_tests is None or self.actual_tests >= self.num_tests:
            return None
        return self.num_tests - self.actual_tests


class MetricSpec(BaseModel):
    """Specification for an evaluation metric."""

    name: str = Field(description="Metric name")
    description: str = Field(
        description=(
            "Two to three sentences on what this metric evaluates, on "
            "what part of the output, and why it matters here. Not a "
            "restatement of the name."
        )
    )
    reuse_status: ReuseStatus = Field(
        default="new",
        description="Whether to reuse, improve, or create this metric",
    )
    existing_id: Optional[str] = Field(
        default=None,
        description="ID of the existing metric when reuse_status is 'reuse' or 'improve'",
    )
    evaluation_prompt: str = Field(
        default="",
        description=(
            "The criteria the judge applies, as they will be sent to "
            "create_metric: something a reader could point at in the "
            "output, one bullet per testable clause, and score bands tied "
            "to conditions rather than adverbs. No template placeholders."
        ),
    )
    evaluation_steps: str = Field(
        default="",
        description=(
            "The ordered steps the judge follows, as they will be sent to "
            "create_metric: 4-7 steps, one observable action each, "
            "scoring last. Use the platform step format — 'Step N:' on "
            "its own line, steps joined by a line containing only '---'."
        ),
    )
    reasoning: str = Field(
        default="",
        description=(
            "The reasoning instructions for the judge, as they will be "
            "sent to create_metric: what evidence to quote, which clause "
            "to tie it to, and how to break a tie between score bands. "
            "Not a note about why the metric is in the plan."
        ),
    )
    explanation: str = Field(
        default="",
        description=(
            "What a passing versus failing result means for the system "
            "under test, and what to do about a fail. Two to four "
            "sentences, sent to create_metric as the result explanation."
        ),
    )
    threshold: float = Field(
        default=1.0,
        description="Pass/fail threshold value",
    )
    threshold_operator: str = Field(
        default=">=",
        description="Comparison operator for threshold",
    )
    target: TargetKind = Field(
        default=TargetKind.TURN,
        description=(
            "What the metric judges, sent to create_metric as config.target.on. "
            '"turn" is the default and judges every turn of a conversation too; '
            '"conversation" judges a whole conversation and never runs on '
            f"Single-Turn tests. Choices: {_TARGET_CHOICES}."
        ),
    )
    completed: bool = Field(
        default=False, description="Whether this metric has been created/resolved"
    )

    @model_validator(mode="before")
    @classmethod
    def _read_legacy_scope(cls, data: Any) -> Any:
        # Plans saved before targets carry metric_scope; Multi-Turn alone judged conversations.
        if isinstance(data, dict) and "target" not in data:
            if data.get("metric_scope") == ["Multi-Turn"]:
                return {**data, "target": TargetKind.CONVERSATION}
        return data


class MappingSpec(BaseModel):
    """Specification for a requirement-to-metric mapping."""

    requirement: str = Field(description="Requirement name")
    metrics: List[str] = Field(
        default_factory=list,
        description="Metric names that evaluate this requirement",
    )
    linked_metrics: List[str] = Field(
        default_factory=list,
        description="Metric names already linked to the requirement (internal progress tracker)",
    )
    completed: bool = Field(
        default=False,
        description="Whether this mapping has been created",
    )


class ArchitectPlan(BaseModel):
    """Complete test suite plan produced by the ArchitectAgent.

    Contains all specifications needed to create test sets,
    metrics, and requirement-metric mappings, optionally grouped
    under a project.
    """

    project: Optional[ProjectSpec] = Field(
        default=None,
        description="Project specification (omit if no project is needed)",
    )
    requirements: List[RequirementSpec] = Field(
        default_factory=list,
        description="Requirement specifications with reuse status",
    )
    test_sets: List[TestSetSpec] = Field(
        default_factory=list,
        description="Test set specifications",
    )
    metrics: List[MetricSpec] = Field(
        default_factory=list,
        description="Metric specifications",
    )
    requirement_metric_mappings: List[MappingSpec] = Field(
        default_factory=list,
        description="Requirement-to-metric mappings to create",
    )

    @field_validator("requirement_metric_mappings", mode="before")
    @classmethod
    def _coerce_mappings(cls, v: Any) -> Any:
        """Accept both legacy dict and new list-of-MappingSpec format."""
        if isinstance(v, dict):
            return [{"requirement": beh, "metrics": mnames} for beh, mnames in v.items()]
        return v

    @model_validator(mode="after")
    def _validate_metric_coverage(self) -> "ArchitectPlan":
        """Ensure every test-set requirement has a linked metric that can judge its tests."""
        if not self.test_sets:
            return self

        requirement_to_metrics: Dict[str, List[str]] = {}
        for mapping in self.requirement_metric_mappings:
            key = mapping.requirement.lower()
            requirement_to_metrics.setdefault(key, []).extend(mapping.metrics)

        targets: Dict[str, TargetKind] = {
            metric.name.lower(): metric.target for metric in self.metrics
        }

        def judges(test_type: str, metric_name: str) -> bool:
            # A metric judging the conversation is never run on a single-turn test.
            target = targets.get(metric_name.lower(), TargetKind.TURN)
            return test_type == "Multi-Turn" or target is not TargetKind.CONVERSATION

        errors: List[str] = []
        for test_set in self.test_sets:
            if not test_set.requirements:
                continue
            for requirement in test_set.requirements:
                requirement_key = requirement.lower()
                linked_metrics = requirement_to_metrics.get(requirement_key, [])
                if not linked_metrics:
                    errors.append(
                        f"Test set '{test_set.name}' ({test_set.test_type}): "
                        f"requirement '{requirement}' has no requirement_metric_mappings entry"
                    )
                    continue

                if not any(judges(test_set.test_type, name) for name in linked_metrics):
                    errors.append(
                        f"Test set '{test_set.name}' ({test_set.test_type}): "
                        f"requirement '{requirement}' is linked only to metrics that judge "
                        f"the conversation — linked: {', '.join(linked_metrics)}"
                    )

        if errors:
            bullet_list = "\n".join(f"- {err}" for err in errors)
            raise ValueError(
                "Metric coverage failed. Every requirement in a test set must have at "
                "least one linked metric that can judge its tests; a metric whose target "
                f'is "conversation" never runs on Single-Turn tests:\n{bullet_list}'
            )
        return self

    def to_markdown(self) -> str:
        """Render the plan as human-readable markdown with task list checkboxes."""
        lines: List[str] = []

        if self.project:
            lines.append(f"# {self.project.name}")
            lines.append("")
            lines.append(self.project.description)
            lines.append("")

        if self.requirements:
            lines.append("## Requirements")
            lines.append("")
            for b in self.requirements:
                box = "[x]" if b.completed else "[ ]"
                tag = f" *({b.reuse_status})*" if b.reuse_status != "new" else ""
                lines.append(f"- {box} **{b.name}**{tag}")
                if b.description:
                    lines.append(f"  {b.description}")
            lines.append("")

        if self.test_sets:
            lines.append("## Test Sets")
            lines.append("")
            for ts in self.test_sets:
                box = "[x]" if ts.completed else "[ ]"
                lines.append(f"- {box} **{ts.name}** — {ts.num_tests} {ts.test_type} tests")
                if ts.requirements:
                    lines.append(f"  Requirements: {', '.join(ts.requirements)}")
                shortfall = ts.shortfall()
                if shortfall is not None:
                    lines.append(
                        f"  WROTE {ts.actual_tests} OF {ts.num_tests} — "
                        f"{shortfall} missing. Say so; do not report "
                        f"{ts.num_tests} tests."
                    )
            lines.append("")

        if self.metrics:
            lines.append("## Metrics")
            lines.append("")
            for m in self.metrics:
                box = "[x]" if m.completed else "[ ]"
                tag = f" *({m.reuse_status})*" if m.reuse_status != "new" else ""
                target = TARGETS[m.target].label
                lines.append(f"- {box} **{m.name}**{tag} — judges: {target}")
                if m.description:
                    lines.append(f"  {m.description}")
            lines.append("")

        if self.requirement_metric_mappings:
            lines.append("## Requirement-Metric Mappings")
            lines.append("")
            for mapping in self.requirement_metric_mappings:
                box = "[x]" if mapping.completed else "[ ]"
                lines.append(f"- {box} **{mapping.requirement}** → {', '.join(mapping.metrics)}")
            lines.append("")

        return "\n".join(lines)


def build_save_plan_tool() -> Dict[str, Any]:
    """Build the ``save_plan`` tool definition from the Pydantic schema.

    Uses ``ArchitectPlan.model_json_schema()`` so the JSON schema
    stays in sync with the model automatically. Internal-only fields
    (like ``completed``) are stripped so the LLM never sees them.
    """
    schema = ArchitectPlan.model_json_schema()
    properties = dict(schema.get("properties", {}))
    defs = schema.get("$defs", {})

    _inline_refs(properties, defs)
    _strip_internal_fields(properties)

    if "project" in properties:
        properties["project"]["description"] = (
            "Project specification. Omit if no project is "
            "needed (e.g. ad-hoc tests for an existing endpoint)."
        )

    pydantic_required = schema.get("required", [])
    required = [k for k in pydantic_required if k != "project"]
    for key in ("requirements", "test_sets", "metrics"):
        if key not in required and key in properties:
            required.append(key)

    return {
        "name": InternalTool.SAVE_PLAN,
        "description": (
            "Save the structured test plan so it persists across "
            "turns. Call this ONCE during the planning phase, right "
            "before presenting the plan to the user. The saved plan "
            "will be injected into every subsequent prompt so you "
            "can follow it exactly during execution."
        ),
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
        ToolMeta.REQUIRES_CONFIRMATION: False,
        ToolMeta.READONLY_HINT: True,
    }


# ── schema helpers ────────────────────────────────────────────────


def _inline_refs(
    obj: Any,
    defs: Dict[str, Any],
) -> None:
    """Recursively replace ``$ref`` pointers with inline definitions."""
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref_name = obj["$ref"].rsplit("/", 1)[-1]
            resolved = defs.get(ref_name, {})
            obj.clear()
            obj.update(resolved)
            _inline_refs(obj, defs)
        else:
            for v in obj.values():
                _inline_refs(v, defs)
    elif isinstance(obj, list):
        for item in obj:
            _inline_refs(item, defs)


def _strip_internal_fields(obj: Any) -> None:
    """Remove fields the LLM should not see (e.g. ``completed``)."""
    if isinstance(obj, dict):
        if "properties" in obj and isinstance(obj["properties"], dict):
            for key in list(obj["properties"]):
                if key in _INTERNAL_FIELDS:
                    del obj["properties"][key]
            if "required" in obj:
                obj["required"] = [r for r in obj["required"] if r not in _INTERNAL_FIELDS]
        for v in obj.values():
            _strip_internal_fields(v)
    elif isinstance(obj, list):
        for item in obj:
            _strip_internal_fields(item)
