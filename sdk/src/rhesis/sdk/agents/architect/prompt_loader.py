"""Jinja environment for Architect prompts with shared skill references."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List, Optional, Sequence

import jinja2

from rhesis.sdk.agents.constants import AgentMode

from .workflow import WorkflowPath

logger = logging.getLogger(__name__)

_ARCHITECT_DIR = Path(__file__).resolve().parent
_SKILLS_REFERENCES_SUFFIX = Path("skills") / "rhesis" / "references"


def resolve_skills_references_dir() -> Optional[Path]:
    """Return skill reference markdown for Architect prompt includes.

    Resolution order:
    1. ``RHESIS_SKILLS_REFERENCES`` env override
    2. Monorepo ``skills/rhesis/references`` (walk up from this module)
    3. Bundled ``prompt_templates/skill_refs`` (populated at wheel build)
    """
    override = os.environ.get("RHESIS_SKILLS_REFERENCES", "").strip()
    if override:
        path = Path(override)
        return path if path.is_dir() else None

    current = _ARCHITECT_DIR
    for _ in range(12):
        references = current / _SKILLS_REFERENCES_SUFFIX
        if references.is_dir():
            return references
        if current.parent == current:
            break
        current = current.parent

    bundled = _ARCHITECT_DIR / "prompt_templates" / "skill_refs"
    if bundled.is_dir():
        return bundled

    logger.warning(
        "skills/rhesis/references not found — Architect prompt includes may be incomplete"
    )
    return None


def build_architect_jinja_env(templates_dir: Path) -> jinja2.Environment:
    """Build a Jinja env that resolves templates from Architect and skill refs."""
    loaders: List[jinja2.BaseLoader] = [jinja2.FileSystemLoader(str(templates_dir))]

    skills_dir = resolve_skills_references_dir()
    if skills_dir is not None:
        loaders.append(jinja2.FileSystemLoader(str(skills_dir)))

    return jinja2.Environment(
        loader=jinja2.ChoiceLoader(loaders),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def phase_include_names(mode: AgentMode, workflow_path: WorkflowPath) -> List[str]:
    """Return template/reference names to inject for this turn."""
    includes: List[str] = []
    wp = workflow_path
    m = mode

    if m == AgentMode.DISCOVERY:
        if wp == WorkflowPath.EXPLORE:
            includes.extend(
                [
                    "phases/discovery.md",
                    "exploration-strategies.md",
                ]
            )
        elif wp == WorkflowPath.PRD:
            includes.append("requirements-workflow.md")
        elif wp == WorkflowPath.RUN_ANALYZE:
            includes.extend(
                [
                    "phases/execution.md",
                    "phases/analysis.md",
                    "result-analysis.md",
                    "insights-summary.md",
                ]
            )
        elif wp == WorkflowPath.DIRECT:
            includes.append("phases/direct-requests.md")
        # UNSET: routing only (system prompt) — no phase block

    elif m == AgentMode.PLANNING:
        includes.extend(
            [
                "phases/planning.md",
                "phases/reuse.md",
                "metric-scope.md",
                "telemachus-save-plan.j2",
            ]
        )
        if wp == WorkflowPath.PRD:
            includes.extend(["requirements-workflow.md", "use-case-bracketfeld.md"])

    elif m == AgentMode.CREATING:
        includes.extend(
            [
                "phases/creation.md",
                "metric-scope.md",
            ]
        )
        if wp == WorkflowPath.PRD:
            includes.append("requirements-workflow.md")

    elif m == AgentMode.EXECUTING:
        includes.extend(
            [
                "phases/execution.md",
                "phases/analysis.md",
                "result-analysis.md",
            ]
        )

    return includes


def render_includes(env: jinja2.Environment, names: Sequence[str]) -> str:
    """Render a list of templates/includes into one markdown block."""
    chunks: List[str] = []
    for name in names:
        try:
            template = env.get_template(name)
            chunks.append(template.render().strip())
        except jinja2.TemplateNotFound:
            logger.warning("Phase include not found: %s", name)
    return "\n\n".join(chunk for chunk in chunks if chunk)


def render_phase_knowledge(
    env: jinja2.Environment,
    mode: AgentMode,
    workflow_path: WorkflowPath,
) -> str:
    """Build phase-specific guidance for the current iteration prompt."""
    names = phase_include_names(mode, workflow_path)
    if not names:
        return ""
    return render_includes(env, names)
