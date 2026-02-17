"""ArchitectPlan and spec models for test suite configuration."""

from typing import Dict, List

from pydantic import BaseModel, Field


class ProjectSpec(BaseModel):
    """Specification for a Rhesis project."""

    name: str = Field(description="Project name")
    description: str = Field(description="Project description")


class TestSetSpec(BaseModel):
    """Specification for a test set within a project."""

    name: str = Field(description="Test set name")
    description: str = Field(description="Detailed test set description")
    short_description: str = Field(default="", description="Brief one-line summary")
    num_tests: int = Field(default=15, description="Number of tests to generate")
    generation_prompt: str = Field(
        default="",
        description="Prompt for test generation",
    )
    behaviors: List[str] = Field(
        default_factory=list,
        description="Behavior tags for this test set",
    )
    categories: List[str] = Field(
        default_factory=list,
        description="Category tags for this test set",
    )
    topics: List[str] = Field(
        default_factory=list,
        description="Topic tags for this test set",
    )


class MetricSpec(BaseModel):
    """Specification for an evaluation metric."""

    name: str = Field(description="Metric name")
    description: str = Field(description="What this metric evaluates")
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


class ArchitectPlan(BaseModel):
    """Complete test suite plan produced by the ArchitectAgent.

    Contains all specifications needed to create a project with
    test sets, metrics, and behavior-metric mappings.
    """

    project: ProjectSpec = Field(description="Project specification")
    test_sets: List[TestSetSpec] = Field(
        default_factory=list,
        description="Test set specifications",
    )
    metrics: List[MetricSpec] = Field(
        default_factory=list,
        description="Metric specifications",
    )
    behavior_descriptions: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of behavior name to description",
    )
    behavior_metric_mappings: Dict[str, List[str]] = Field(
        default_factory=dict,
        description=("Map of behavior name to list of metric names that evaluate it"),
    )

    def to_markdown(self) -> str:
        """Render the plan as human-readable markdown."""
        lines: List[str] = []

        # Project
        lines.append(f"# {self.project.name}")
        lines.append("")
        lines.append(self.project.description)
        lines.append("")

        # Test Sets
        if self.test_sets:
            lines.append("## Test Sets")
            lines.append("")
            for ts in self.test_sets:
                lines.append(f"### {ts.name}")
                lines.append("")
                lines.append(ts.description)
                lines.append("")
                lines.append(f"- **Tests to generate:** {ts.num_tests}")
                if ts.behaviors:
                    lines.append(f"- **Behaviors:** {', '.join(ts.behaviors)}")
                if ts.categories:
                    lines.append(f"- **Categories:** {', '.join(ts.categories)}")
                if ts.topics:
                    lines.append(f"- **Topics:** {', '.join(ts.topics)}")
                lines.append("")

        # Metrics
        if self.metrics:
            lines.append("## Metrics")
            lines.append("")
            for m in self.metrics:
                lines.append(f"### {m.name}")
                lines.append("")
                lines.append(m.description)
                if m.reasoning:
                    lines.append("")
                    lines.append(f"**Reasoning:** {m.reasoning}")
                lines.append("")
                lines.append(f"- **Threshold:** {m.threshold_operator} {m.threshold}")
                lines.append("")

        # Behavior-metric mappings
        if self.behavior_metric_mappings:
            lines.append("## Behavior-Metric Mappings")
            lines.append("")
            for behavior, metric_names in self.behavior_metric_mappings.items():
                desc = self.behavior_descriptions.get(behavior, "")
                lines.append(f"### {behavior}")
                if desc:
                    lines.append("")
                    lines.append(desc)
                lines.append("")
                lines.append(f"- **Metrics:** {', '.join(metric_names)}")
                lines.append("")

        return "\n".join(lines)
