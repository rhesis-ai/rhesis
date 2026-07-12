"""ArchitectPlan and spec models for test suite configuration."""

from typing import Any, Dict, List, Literal, Optional, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from rhesis.sdk.agents.constants import InternalTool, ToolMeta

ReuseStatus = Literal["reuse", "improve", "new"]
MetricScope = Literal["Single-Turn", "Multi-Turn"]
_VALID_METRIC_SCOPES = frozenset({"Single-Turn", "Multi-Turn"})

# Fields that track execution progress and must never be written by the LLM.
# Referenced by _strip_internal_fields (JSON schema builder) and
# MappingSpec._guard_internal_fields (runtime validator).
_INTERNAL_FIELDS: frozenset = frozenset({"completed", "linked_metrics"})


class ProjectSpec(BaseModel):
    """Specification for a Rhesis project."""

    name: str = Field(description="Project name")
    description: str = Field(description="Project description")
    completed: bool = Field(default=False, description="Whether this project has been created")


class BehaviorSpec(BaseModel):
    """Specification for a behavior in the plan."""

    name: str = Field(description="Behavior name")
    description: str = Field(default="", description="What this behavior expects")
    reuse_status: ReuseStatus = Field(
        default="new",
        description="Whether to reuse an existing behavior, or create a new one",
    )
    existing_id: Optional[str] = Field(
        default=None,
        description="ID of the existing behavior when reuse_status is 'reuse'",
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
        description='Must be exactly "Single-Turn" or "Multi-Turn"',
    )
    generation_prompt: str = Field(
        default="",
        description="Prompt for test generation",
    )
    behaviors: List[str] = Field(
        default_factory=list,
        description="Behavior names this test set targets",
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


class MetricSpec(BaseModel):
    """Specification for an evaluation metric."""

    name: str = Field(description="Metric name")
    description: str = Field(description="What this metric evaluates")
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
        description="Prompt for LLM-based evaluation",
    )
    evaluation_steps: str = Field(
        default="",
        description="Step-by-step evaluation procedure",
    )
    reasoning: str = Field(
        default="",
        description="Why this metric is needed",
    )
    threshold: float = Field(
        default=1.0,
        description="Pass/fail threshold value",
    )
    threshold_operator: str = Field(
        default=">=",
        description="Comparison operator for threshold",
    )
    metric_scope: List[MetricScope] = Field(
        default_factory=lambda: ["Single-Turn"],
        description=(
            'Which test types this metric can evaluate. Each entry must be '
            'exactly "Single-Turn" or "Multi-Turn". Use ["Single-Turn"] for '
            "one-shot prompts; [\"Multi-Turn\"] for conversational goals; "
            'both only when the same rubric applies to either shape.'
        ),
        min_length=1,
    )
    completed: bool = Field(
        default=False, description="Whether this metric has been created/resolved"
    )

    @field_validator("metric_scope")
    @classmethod
    def _validate_metric_scope_values(cls, value: List[str]) -> List[str]:
        invalid = [entry for entry in value if entry not in _VALID_METRIC_SCOPES]
        if invalid:
            allowed = ", ".join(sorted(_VALID_METRIC_SCOPES))
            raise ValueError(
                f"metric_scope entries must be {allowed}; got invalid: {invalid}"
            )
        return value


class MappingSpec(BaseModel):
    """Specification for a behavior-to-metric mapping."""

    behavior: str = Field(description="Behavior name")
    metrics: List[str] = Field(
        default_factory=list,
        description="Metric names that evaluate this behavior",
    )
    linked_metrics: List[str] = Field(
        default_factory=list,
        description="Metric names already linked to the behavior (internal progress tracker)",
    )
    completed: bool = Field(
        default=False,
        description="Whether this mapping has been created",
    )


class ArchitectPlan(BaseModel):
    """Complete test suite plan produced by the ArchitectAgent.

    Contains all specifications needed to create test sets,
    metrics, and behavior-metric mappings, optionally grouped
    under a project.
    """

    project: Optional[ProjectSpec] = Field(
        default=None,
        description="Project specification (omit if no project is needed)",
    )
    behaviors: List[BehaviorSpec] = Field(
        default_factory=list,
        description="Behavior specifications with reuse status",
    )
    test_sets: List[TestSetSpec] = Field(
        default_factory=list,
        description="Test set specifications",
    )
    metrics: List[MetricSpec] = Field(
        default_factory=list,
        description="Metric specifications",
    )
    behavior_metric_mappings: List[MappingSpec] = Field(
        default_factory=list,
        description="Behavior-to-metric mappings to create",
    )

    @field_validator("behavior_metric_mappings", mode="before")
    @classmethod
    def _coerce_mappings(cls, v: Any) -> Any:
        """Accept both legacy dict and new list-of-MappingSpec format."""
        if isinstance(v, dict):
            return [{"behavior": beh, "metrics": mnames} for beh, mnames in v.items()]
        return v

    @model_validator(mode="after")
    def _validate_metric_scope_coverage(self) -> Self:
        """Ensure every test-set behavior has a compatible linked metric."""
        if not self.test_sets:
            return self

        behavior_to_metrics: Dict[str, List[str]] = {}
        for mapping in self.behavior_metric_mappings:
            key = mapping.behavior.lower()
            behavior_to_metrics.setdefault(key, []).extend(mapping.metrics)

        metric_scopes: Dict[str, List[str]] = {
            metric.name.lower(): list(metric.metric_scope) for metric in self.metrics
        }

        errors: List[str] = []
        for test_set in self.test_sets:
            if not test_set.behaviors:
                continue
            for behavior in test_set.behaviors:
                behavior_key = behavior.lower()
                linked_metrics = behavior_to_metrics.get(behavior_key, [])
                if not linked_metrics:
                    errors.append(
                        f"Test set '{test_set.name}' ({test_set.test_type}): "
                        f"behavior '{behavior}' has no behavior_metric_mappings entry"
                    )
                    continue

                compatible = [
                    metric_name
                    for metric_name in linked_metrics
                    if test_set.test_type
                    in metric_scopes.get(metric_name.lower(), [])
                ]
                if not compatible:
                    scope_details = ", ".join(
                        f"{name} ({metric_scopes.get(name.lower(), [])})"
                        for name in linked_metrics
                    )
                    errors.append(
                        f"Test set '{test_set.name}' ({test_set.test_type}): "
                        f"behavior '{behavior}' is linked only to metrics whose "
                        f"metric_scope does not include '{test_set.test_type}' "
                        f"— linked: {scope_details}"
                    )

        if errors:
            bullet_list = "\n".join(f"- {err}" for err in errors)
            raise ValueError(
                "Metric scope coverage failed. Every behavior in a test set "
                "must have at least one linked metric whose metric_scope "
                f"includes that test set's test_type:\n{bullet_list}"
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

        if self.behaviors:
            lines.append("## Behaviors")
            lines.append("")
            for b in self.behaviors:
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
                if ts.behaviors:
                    lines.append(f"  Behaviors: {', '.join(ts.behaviors)}")
            lines.append("")

        if self.metrics:
            lines.append("## Metrics")
            lines.append("")
            for m in self.metrics:
                box = "[x]" if m.completed else "[ ]"
                tag = f" *({m.reuse_status})*" if m.reuse_status != "new" else ""
                scope = ", ".join(m.metric_scope) if m.metric_scope else "unset"
                lines.append(f"- {box} **{m.name}**{tag} — scope: {scope}")
            lines.append("")

        if self.behavior_metric_mappings:
            lines.append("## Behavior-Metric Mappings")
            lines.append("")
            for mapping in self.behavior_metric_mappings:
                box = "[x]" if mapping.completed else "[ ]"
                lines.append(f"- {box} **{mapping.behavior}** → {', '.join(mapping.metrics)}")
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
    for key in ("behaviors", "test_sets", "metrics"):
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
