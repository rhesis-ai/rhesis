"""Tests for lazy phase prompt loading."""

import shutil
from pathlib import Path

import pytest

from rhesis.sdk.agents.architect.prompt_loader import (
    build_architect_jinja_env,
    phase_include_names,
    render_phase_knowledge,
)
from rhesis.sdk.agents.architect.workflow import (
    WorkflowPath,
    infer_workflow_path,
    resolve_workflow_path_update,
)
from rhesis.sdk.agents.constants import AgentMode

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATES_DIR = (
    _REPO_ROOT / "sdk" / "src" / "rhesis" / "sdk" / "agents" / "architect" / "prompt_templates"
)
_SKILLS_REFS = _REPO_ROOT / "skills" / "rhesis" / "references"


@pytest.mark.unit
class TestInferWorkflowPath:
    def test_menu_quick(self):
        assert infer_workflow_path("1") == WorkflowPath.EXPLORE

    def test_menu_prd(self):
        assert infer_workflow_path("3 — build test foundation from PRD") == WorkflowPath.PRD

    def test_menu_run_analyze(self):
        assert infer_workflow_path("4 run or analyze") == WorkflowPath.RUN_ANALYZE

    def test_prd_attachment(self):
        msg = "x" * 250
        assert infer_workflow_path(msg, has_attachments=True) == WorkflowPath.PRD

    def test_direct_list(self):
        assert infer_workflow_path("list my test sets") == WorkflowPath.DIRECT

    def test_ambiguous_returns_none(self):
        assert infer_workflow_path("hello") is None


@pytest.mark.unit
class TestResolveWorkflowPathUpdate:
    def test_unset_to_inferred(self):
        assert resolve_workflow_path_update(WorkflowPath.UNSET, "1") == WorkflowPath.EXPLORE

    def test_explore_overridden_by_prd_paste(self):
        msg = "Functional requirement: " + ("x" * 500)
        assert resolve_workflow_path_update(WorkflowPath.EXPLORE, msg) == WorkflowPath.PRD

    def test_prd_not_overridden_by_ambiguous(self):
        assert resolve_workflow_path_update(WorkflowPath.PRD, "hello") is None

    def test_explore_not_overridden_by_another_explore_signal(self):
        assert resolve_workflow_path_update(WorkflowPath.EXPLORE, "explore my endpoint") is None


@pytest.mark.unit
class TestPhaseIncludeNames:
    def test_unset_discovery_empty(self):
        assert phase_include_names(AgentMode.DISCOVERY, WorkflowPath.UNSET) == []

    def test_explore_discovery_has_exploration(self):
        names = phase_include_names(AgentMode.DISCOVERY, WorkflowPath.EXPLORE)
        assert "phases/discovery.md" in names
        assert "exploration-strategies.md" in names
        assert "odata-patterns.md" not in names
        assert "telemachus-guidelines.j2" not in names

    def test_planning_prd_has_prd_workflow_and_bracketfeld(self):
        names = phase_include_names(AgentMode.PLANNING, WorkflowPath.PRD)
        assert "prd-workflow.md" in names
        assert "use-case-bracketfeld.md" in names
        assert "phases/reuse.md" in names
        assert "telemachus-save-plan.j2" in names
        assert "telemachus-reuse.j2" not in names

    def test_creating_no_duplicate_creation_j2(self):
        names = phase_include_names(AgentMode.CREATING, WorkflowPath.PRD)
        assert "phases/creation.md" in names
        assert "telemachus-creation-order.j2" not in names

    def test_executing_has_analysis(self):
        names = phase_include_names(AgentMode.EXECUTING, WorkflowPath.EXPLORE)
        assert "phases/analysis.md" in names


@pytest.mark.unit
class TestRenderPhaseKnowledge:
    def test_render_discovery_explore(self):
        env = build_architect_jinja_env(_TEMPLATES_DIR)
        text = render_phase_knowledge(env, AgentMode.DISCOVERY, WorkflowPath.EXPLORE)
        assert "explore_endpoint" in text.lower()
        assert len(text) > 100

    def test_unset_discovery_empty(self):
        env = build_architect_jinja_env(_TEMPLATES_DIR)
        assert render_phase_knowledge(env, AgentMode.DISCOVERY, WorkflowPath.UNSET) == ""


@pytest.mark.unit
class TestBundledSkillReferences:
    def test_render_system_prompt_with_bundled_refs_only(self, tmp_path, monkeypatch):
        """Production path: bundled skill_refs without monorepo checkout."""
        templates_dir = tmp_path / "templates"
        bundled = templates_dir / "skill_refs"
        shutil.copytree(_SKILLS_REFS, bundled)

        for name in (
            "system_prompt.j2",
            "personality.j2",
            "workflow-routing.j2",
            "telemachus-guidelines.j2",
            "telemachus-resolution.j2",
            "telemachus-security.j2",
        ):
            shutil.copy2(_TEMPLATES_DIR / name, templates_dir / name)

        monkeypatch.delenv("RHESIS_SKILLS_REFERENCES", raising=False)
        monkeypatch.setattr(
            "rhesis.sdk.agents.architect.prompt_loader.resolve_skills_references_dir",
            lambda: bundled,
        )

        env = build_architect_jinja_env(templates_dir)
        text = env.get_template("system_prompt.j2").render()
        assert "Behavior" in text
        assert "OData" in text
        assert "confirm" in text.lower()

    def test_wheel_includes_skill_refs(self):
        """Verify hatch force-include packages references into the wheel."""
        import subprocess
        import zipfile

        result = subprocess.run(
            ["uv", "build", "--wheel"],
            cwd=_REPO_ROOT / "sdk",
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.returncode == 0

        dist_dir = _REPO_ROOT / "sdk" / "dist"
        wheels = sorted(dist_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
        assert wheels, "No wheel produced"
        with zipfile.ZipFile(wheels[0]) as zf:
            names = zf.namelist()
        assert any(n.endswith("prompt_templates/skill_refs/entity-model.md") for n in names), (
            f"skill refs missing from wheel: {[n for n in names if 'skill_refs' in n][:5]}"
        )
