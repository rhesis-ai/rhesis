"""ArchitectPlan and spec models for test suite configuration."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from rhesis.sdk.agents.constants import InternalTool, ToolMeta

ReuseStatus = Literal["reuse", "improve", "new"]


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
    test_type: str = Field(
        default="Single-Turn",
        description="Single-Turn or Multi-Turn",
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
    completed: bool = Field(
        default=False, description="Whether this metric has been created/resolved"
    )


class MappingSpec(BaseModel):
    """Specification for a behavior-to-metric mapping."""

    behavior: str = Field(description="Behavior name")
    metrics: List[str] = Field(
        default_factory=list,
        description="Metric names that evaluate this behavior",
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
                lines.append(f"- {box} **{m.name}**{tag}")
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

_INTERNAL_FIELDS = {"completed"}


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
