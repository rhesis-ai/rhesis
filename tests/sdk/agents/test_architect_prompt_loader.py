"""Tests for lazy phase prompt loading."""

import pytest

from rhesis.sdk.agents.architect.prompt_loader import (
    phase_include_names,
    render_phase_knowledge,
)
from rhesis.sdk.agents.architect.workflow import WorkflowPath, infer_workflow_path
from rhesis.sdk.agents.constants import AgentMode


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
class TestPhaseIncludeNames:
    def test_unset_discovery_empty(self):
        assert phase_include_names(AgentMode.DISCOVERY, WorkflowPath.UNSET) == []

    def test_explore_discovery_has_exploration(self):
        names = phase_include_names(AgentMode.DISCOVERY, WorkflowPath.EXPLORE)
        assert "phases/discovery.md" in names
        assert "exploration-strategies.md" in names

    def test_planning_prd_has_prd_workflow(self):
        names = phase_include_names(AgentMode.PLANNING, WorkflowPath.PRD)
        assert "prd-workflow.md" in names
        assert "telemachus-save-plan.j2" in names

    def test_executing_has_analysis(self):
        names = phase_include_names(AgentMode.EXECUTING, WorkflowPath.EXPLORE)
        assert "phases/analysis.md" in names


@pytest.mark.unit
class TestRenderPhaseKnowledge:
    def test_render_discovery_explore(self):
        from pathlib import Path

        from rhesis.sdk.agents.architect.prompt_loader import build_architect_jinja_env

        env = build_architect_jinja_env(
            Path(__file__).resolve().parents[4]
            / "src"
            / "rhesis"
            / "sdk"
            / "agents"
            / "architect"
            / "prompt_templates"
        )
        text = render_phase_knowledge(env, AgentMode.DISCOVERY, WorkflowPath.EXPLORE)
        assert "explore_endpoint" in text.lower()
        assert len(text) > 100

    def test_unset_discovery_empty(self):
        from pathlib import Path

        from rhesis.sdk.agents.architect.prompt_loader import build_architect_jinja_env

        env = build_architect_jinja_env(
            Path(__file__).resolve().parents[4]
            / "src"
            / "rhesis"
            / "sdk"
            / "agents"
            / "architect"
            / "prompt_templates"
        )
        assert render_phase_knowledge(env, AgentMode.DISCOVERY, WorkflowPath.UNSET) == ""
