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
        assert "spec-workflow.md" in names
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

    def test_discovery_flags_a_project_with_no_endpoint(self):
        # Discovery is where the endpoint gets resolved, so the "none at all"
        # case has to be handled here too — not only in the system prompt.
        env = build_architect_jinja_env(_TEMPLATES_DIR)
        text = render_phase_knowledge(env, AgentMode.DISCOVERY, WorkflowPath.EXPLORE)
        assert "no** endpoint at all" in text
        assert "connecting-application" in text


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
        assert "Requirement" in text
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

    Both templates previously told the agent that requirements and metrics had
    no detail pages. Both do, so the agent was suppressing links a user
    could have followed — and the two files disagreed with each other.
    """

    TEMPLATES = ("telemachus-guidelines.j2", "streaming_response.j2")
    # Entities the prompts tell the agent to link.
    LINKED = ("test-sets", "tests", "endpoints", "projects", "test-runs", "requirements", "metrics")

    @pytest.mark.parametrize("segment", LINKED)
    def test_linked_entities_really_have_detail_pages(self, segment):
        assert _has_detail_page(segment), (
            f"prompts link /{segment}/<id> but no [identifier] route exists"
        )

    def test_test_results_still_has_no_detail_page(self):
        """The one negative claim the prompts make must stay true."""
        assert not _has_detail_page("test-results")

    @pytest.mark.parametrize("template", TEMPLATES)
    def test_templates_do_not_deny_requirement_or_metric_pages(self, template):
        text = (_TEMPLATES_DIR / template).read_text()
        for stale in (
            "Requirements, metrics and test results do NOT have detail pages",
            "Requirements and test results do NOT have detail pages",
        ):
            assert stale not in text, f"{template} still carries stale claim: {stale!r}"

    @pytest.mark.parametrize("template", TEMPLATES)
    def test_templates_document_requirement_and_metric_links(self, template):
        text = (_TEMPLATES_DIR / template).read_text()
        assert "/requirements/" in text, f"{template} never shows a requirement link"
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


@pytest.mark.unit
class TestProjectContextBlock:
    """The agent must be told which project it is in.

    It cannot work this out: ``project`` is not covered by the
    ``project_isolation`` RLS policy, so ``list_projects`` returns every
    project in the organization with nothing marking the active one. Without
    the injected block the agent asked the user on every session.
    """

    def _render(self, **ctx):
        env = build_architect_jinja_env(_TEMPLATES_DIR)
        base = {
            "mode": "discovery",
            "workflow_path": "unset",
            "user_query": "I need a test set",
            "tools_text": "",
        }
        return env.get_template("iteration_prompt.j2").render(**{**base, **ctx})

    def test_block_names_the_project(self):
        text = self._render(project_context_text="Project: Travel Agent\nProject ID: abc-123")
        assert "Travel Agent" in text
        assert "do not ask" in text.lower()

    def test_block_forbids_resolving_a_project(self):
        text = self._render(project_context_text="Project: Travel Agent")
        assert "do not call `list_projects` to pick one" in text
        assert "omit `project_id`" in text

    def test_block_is_honest_about_org_level_rows(self):
        """RLS matches project_id = current OR project_id IS NULL.

        Claiming the agent sees only this project's rows would make it give
        the wrong reason for why an org-level entity showed up.
        """
        text = self._render(project_context_text="Project: Travel Agent")
        assert "organization-level" in text

    def test_block_admits_other_projects_are_unreadable(self):
        text = self._render(project_context_text="Project: Travel Agent")
        assert "cannot read or write" in text
        assert "empty result" in text

    def test_no_block_without_a_project(self):
        """Sessions with no project must render exactly as before."""
        text = self._render(project_context_text="")
        assert "Current Project" not in text
        assert "do not call `list_projects`" not in text
