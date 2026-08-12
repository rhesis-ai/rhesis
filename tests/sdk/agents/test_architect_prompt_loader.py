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

    def test_insights_summarize_signals(self):
        assert (
            infer_workflow_path("Summarize insights for the Insights page view")
            == WorkflowPath.RUN_ANALYZE
        )
        assert infer_workflow_path("insights summary — Chatbot") == WorkflowPath.RUN_ANALYZE


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
        assert "requirements-workflow.md" in names
        assert "use-case-bracketfeld.md" in names
        assert "phases/reuse.md" in names
        assert "telemachus-save-plan.j2" in names
        assert "telemachus-reuse.j2" not in names

    def test_creating_no_duplicate_creation_j2(self):
        names = phase_include_names(AgentMode.CREATING, WorkflowPath.PRD)
        assert "phases/creation.md" in names
        assert "telemachus-creation-order.j2" not in names

    def test_metric_authoring_loaded_when_metrics_are_written(self):
        # Metric field depth is only actionable while planning or creating them.
        for mode in (AgentMode.PLANNING, AgentMode.CREATING):
            assert "metric-authoring.md" in phase_include_names(mode, WorkflowPath.EXPLORE)
        assert "metric-authoring.md" not in phase_include_names(
            AgentMode.EXECUTING, WorkflowPath.EXPLORE
        )

    def test_executing_has_analysis(self):
        names = phase_include_names(AgentMode.EXECUTING, WorkflowPath.EXPLORE)
        assert "phases/analysis.md" in names

    def test_run_analyze_discovery_includes_insights_summary(self):
        names = phase_include_names(AgentMode.DISCOVERY, WorkflowPath.RUN_ANALYZE)
        assert "insights-summary.md" in names
        assert "result-analysis.md" in names
        assert "phases/analysis.md" in names

    def test_run_analyze_executing_keeps_insights_summary(self):
        # The first get_test_result_stats call switches the mode to EXECUTING;
        # the Insights handoff guidance must stay loaded so the agent keeps
        # aggregating across all runs instead of falling back to single-run
        # patterns.
        names = phase_include_names(AgentMode.EXECUTING, WorkflowPath.RUN_ANALYZE)
        assert "insights-summary.md" in names
        assert "result-analysis.md" in names

    def test_executing_non_run_analyze_omits_insights_summary(self):
        names = phase_include_names(AgentMode.EXECUTING, WorkflowPath.EXPLORE)
        assert "insights-summary.md" not in names


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

    def test_creating_phase_carries_the_metric_step_format(self):
        env = build_architect_jinja_env(_TEMPLATES_DIR)
        text = render_phase_knowledge(env, AgentMode.CREATING, WorkflowPath.EXPLORE)
        assert "Step 1:" in text
        assert "evaluation_steps" in text


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


_FRONTEND_ROUTES = _REPO_ROOT / "apps" / "frontend" / "src" / "app" / "(protected)"


def _has_detail_page(segment: str) -> bool:
    """True when the frontend has a dynamic detail route for this segment."""
    return (_FRONTEND_ROUTES / segment / "[identifier]").is_dir()


@pytest.mark.unit
@pytest.mark.skipif(
    not _FRONTEND_ROUTES.is_dir(),
    reason="frontend tree not present (SDK checked out standalone)",
)
class TestEntityLinkGuidanceMatchesFrontend:
    """Keep link guidance honest about which entities have detail pages.

    Both templates previously told the agent that behaviors and metrics had
    no detail pages. Both do, so the agent was suppressing links a user
    could have followed — and the two files disagreed with each other.
    """

    TEMPLATES = ("telemachus-guidelines.j2", "streaming_response.j2")
    # Entities the prompts tell the agent to link.
    LINKED = ("test-sets", "tests", "endpoints", "projects", "test-runs", "behaviors", "metrics")

    @pytest.mark.parametrize("segment", LINKED)
    def test_linked_entities_really_have_detail_pages(self, segment):
        assert _has_detail_page(segment), (
            f"prompts link /{segment}/<id> but no [identifier] route exists"
        )

    def test_test_results_still_has_no_detail_page(self):
        """The one negative claim the prompts make must stay true."""
        assert not _has_detail_page("test-results")

    @pytest.mark.parametrize("template", TEMPLATES)
    def test_templates_do_not_deny_behavior_or_metric_pages(self, template):
        text = (_TEMPLATES_DIR / template).read_text()
        for stale in (
            "Behaviors, metrics and test results do NOT have detail pages",
            "Behaviors and test results do NOT have detail pages",
        ):
            assert stale not in text, f"{template} still carries stale claim: {stale!r}"

    @pytest.mark.parametrize("template", TEMPLATES)
    def test_templates_document_behavior_and_metric_links(self, template):
        text = (_TEMPLATES_DIR / template).read_text()
        assert "/behaviors/" in text, f"{template} never shows a behavior link"
        assert "/metrics/" in text, f"{template} never shows a metric link"

    @pytest.mark.parametrize("template", TEMPLATES)
    def test_trace_links_specify_the_resolvable_id(self, template):
        """/traces/<id> resolves a span DB UUID, not the OTel trace_id.

        The frontend route calls lookupSpan(identifier) against
        GET /telemetry/spans/{span_db_id}/lookup, typed UUID. Since
        list_annotations returns both ids, guidance that just says "id"
        invites a broken link.
        """
        text = (_TEMPLATES_DIR / template).read_text()
        if "/traces/" not in text:
            pytest.skip(f"{template} does not document trace links")
        assert "trace_db_id" in text, (
            f"{template} documents trace links without naming trace_db_id — "
            "the agent may use trace_id, which does not resolve"
        )
