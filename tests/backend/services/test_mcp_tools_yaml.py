"""Tests that mcp_tools.yaml contains expected tools and valid structure."""

import importlib.util
import re
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MCP_TOOLS_YAML = _REPO_ROOT / "apps/backend/src/rhesis/backend/app/mcp_server/mcp_tools.yaml"
_MCP_SCHEMA_PY = _REPO_ROOT / "apps/backend/src/rhesis/backend/app/mcp_server/schema.py"


def load_tool_configs():
    with open(_MCP_TOOLS_YAML) as f:
        return yaml.safe_load(f).get("tools", [])


def _load_schema_module():
    spec = importlib.util.spec_from_file_location("mcp_schema_module", _MCP_SCHEMA_PY)
    assert spec and spec.loader, f"Could not load schema module from {_MCP_SCHEMA_PY}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
class TestExploreEndpointInMcpTools:
    def test_explore_endpoint_in_yaml(self):
        names = [tc["name"] for tc in load_tool_configs()]
        assert "explore_endpoint" in names

    def test_explore_endpoint_is_post(self):
        configs = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = configs["explore_endpoint"]
        assert cfg["method"].upper() == "POST"
        assert "/explore" in cfg["path"]

    def test_explore_endpoint_requires_confirmation(self):
        configs = {tc["name"]: tc for tc in load_tool_configs()}
        assert configs["explore_endpoint"].get("requires_confirmation") is True

    def test_explore_endpoint_has_strategy_and_goal_params(self):
        cfg = {tc["name"]: tc for tc in load_tool_configs()}["explore_endpoint"]
        params = cfg.get("parameters", {})
        assert "strategy" in params
        assert "goal" in params


@pytest.mark.unit
class TestInputSchemaPropertyNames:
    def test_dollar_prefixed_params_are_sanitized(self):
        build_input_schema = _load_schema_module().build_input_schema
        operation = {
            "parameters": [
                {"name": "$filter", "in": "query", "schema": {"type": "string"}},
                {"name": "$select", "in": "query", "schema": {"type": "string"}},
                {"name": "source_id", "in": "path", "required": True},
            ]
        }
        schema = build_input_schema(operation, {}, {})
        props = schema["properties"]
        assert "filter" in props and "$filter" not in props
        assert "select" in props and "$select" not in props
        assert schema["required"] == ["source_id"]

    def test_yaml_override_keyed_by_sanitized_name_applies(self):
        build_input_schema = _load_schema_module().build_input_schema
        operation = {
            "parameters": [
                {"name": "$filter", "in": "query", "schema": {"type": "string"}},
            ]
        }
        schema = build_input_schema(operation, {}, {"filter": {"description": "search by title"}})
        assert schema["properties"]["filter"]["description"] == "search by title"


@pytest.mark.unit
class TestNewMcpToolsPresent:
    NEW_TOOLS = frozenset(
        {
            "get_test_set",
            "list_test_set_tests",
            "get_endpoint",
            "get_metric",
            "create_source",
            "update_metric",
            "remove_requirement_from_metric",
            "update_test_set",
            "get_test",
            "update_test",
            "get_requirement",
            "get_test_set_last_run",
            "get_test_set_metrics",
            "get_project",
        }
    )

    def test_new_tools_in_yaml(self):
        names = {tc["name"] for tc in load_tool_configs()}
        missing = self.NEW_TOOLS - names
        assert not missing, f"Missing tools: {sorted(missing)}"


@pytest.mark.unit
class TestTagMcpToolsPresent:
    TAG_TOOLS = frozenset({"list_tags", "assign_tag"})

    def test_tag_tools_in_yaml(self):
        names = {tc["name"] for tc in load_tool_configs()}
        missing = self.TAG_TOOLS - names
        assert not missing, f"Missing tag tools: {sorted(missing)}"

    def test_assign_tag_path_and_method(self):
        by_name = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = by_name["assign_tag"]
        assert cfg["method"].upper() == "POST"
        assert cfg["path"] == "/tags/{entity_type}/{entity_id}"

    def test_list_tags_default_query_select(self):
        by_name = {tc["name"]: tc for tc in load_tool_configs()}
        cfg = by_name["list_tags"]
        assert cfg.get("default_query", {}).get("$select") == "id,name"

    def test_assign_tag_requires_confirmation(self):
        by_name = {tc["name"]: tc for tc in load_tool_configs()}
        assert by_name["assign_tag"].get("requires_confirmation") is True


@pytest.mark.unit
class TestListAnnotationsTool:
    """The annotations tool is how the architect sees human feedback."""

    def _cfg(self):
        return {tc["name"]: tc for tc in load_tool_configs()}["list_annotations"]

    def test_list_annotations_in_yaml(self):
        names = {tc["name"] for tc in load_tool_configs()}
        assert "list_annotations" in names

    def test_list_annotations_is_read_only_get(self):
        cfg = self._cfg()
        assert cfg["method"].upper() == "GET"
        # GET gets readOnlyHint automatically, so it must not be confirmation-gated.
        assert "requires_confirmation" not in cfg

    def test_list_annotations_path_has_trailing_slash(self):
        # Must match the OpenAPI path key exactly or the tool is silently skipped.
        assert self._cfg()["path"] == "/annotations/"

    def test_list_annotations_declares_page_size(self):
        page_size = self._cfg().get("page_size")
        assert page_size is not None
        # peek-ahead sends limit=page_size+1, which must stay within the
        # endpoint's le=100 cap.
        assert page_size + 1 <= 100

    def test_list_annotations_description_documents_scoping(self):
        description = self._cfg()["description"]
        for token in ("test_run_id", "entity_type", "test_result_id", "trace_db_id"):
            assert token in description, f"description should explain {token}"

    def test_list_annotations_input_schema_exposes_filters(self):
        """Build the schema from the real app so a path/param drift fails here."""
        from rhesis.backend.app.main import app
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        tools, operations = build_tools_and_operations(app)
        by_name = {t.name: t for t in tools}
        assert "list_annotations" in by_name, (
            "tool absent — path likely does not match any OpenAPI route"
        )

        props = by_name["list_annotations"].inputSchema["properties"]
        for param in (
            "test_run_id",
            "entity_type",
            "resolved",
            "rating",
            "target_type",
            "search",
            "skip",
        ):
            assert param in props, f"{param} missing from tool schema"

        # page_size means the server owns pagination.
        assert "limit" not in props
        assert operations["list_annotations"]["method"] == "GET"

    def test_list_annotations_is_readonly_hinted(self):
        from rhesis.backend.app.main import app
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        tools, _ = build_tools_and_operations(app)
        tool = {t.name: t for t in tools}["list_annotations"]
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False


@pytest.mark.unit
class TestAnnotationWriteTools:
    """Reading annotations is not enough; the architect can record one too.

    These are the only annotation tools that write, so the confirmation gate
    and the target shape are what matter here.
    """

    def _cfg(self, name):
        return {tc["name"]: tc for tc in load_tool_configs()}[name]

    def _built(self):
        from rhesis.backend.app.main import app
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        tools, operations = build_tools_and_operations(app)
        return {t.name: t for t in tools}, operations

    @pytest.mark.parametrize("name", ["get_annotation", "create_annotation", "update_annotation"])
    def test_the_tool_resolves_against_a_real_route(self, name):
        """A path that matches no OpenAPI route makes the tool vanish silently."""
        by_name, _ = self._built()
        assert name in by_name, f"{name} absent — path likely matches no route"

    @pytest.mark.parametrize("name", ["create_annotation", "update_annotation"])
    def test_writes_are_confirmation_gated(self, name):
        assert self._cfg(name).get("requires_confirmation") is True

    @pytest.mark.parametrize("name", ["create_annotation", "update_annotation"])
    def test_writes_are_not_hinted_read_only(self, name):
        by_name, _ = self._built()
        assert by_name[name].annotations.readOnlyHint is not True

    def test_get_annotation_is_read_only(self):
        cfg = self._cfg("get_annotation")
        assert cfg["method"].upper() == "GET"
        assert "requires_confirmation" not in cfg

    def test_create_exposes_the_parent_and_the_verdict(self):
        by_name, operations = self._built()
        props = by_name["create_annotation"].inputSchema["properties"]
        for param in ("entity_type", "entity_id", "status_id", "comments", "target"):
            assert param in props, f"{param} missing from create_annotation schema"
        assert operations["create_annotation"]["method"] == "POST"

    def test_create_warns_off_the_flat_target_shape(self):
        """Responses carry target flat; sending that on a write is ignored.

        A model copying `target_type` from a list_annotations row into a create
        call would land an annotation on the whole entity instead of the metric
        it named, with no error, so the parameter doc has to say so.
        """
        target_doc = self._cfg("create_annotation")["parameters"]["target"]["description"]
        assert "target_type" in target_doc
        assert "metric" in target_doc and "turn" in target_doc

    def test_create_says_whose_judgement_it_is(self):
        """An annotation is attributed to a person, not to the model."""
        description = self._cfg("create_annotation")["description"]
        assert "own initiative" in description or "own opinion" in description

    def test_create_says_it_overrides_the_parent(self):
        description = self._cfg("create_annotation")["description"]
        assert "OVERRIDES" in description or "overrides" in description

    def test_update_documents_the_author_only_rule(self):
        description = self._cfg("update_annotation")["description"]
        assert "author" in description

    def test_the_odata_filter_override_is_keyed_without_the_dollar(self):
        """Overrides are matched on the sanitized property name.

        Keyed as `$filter`, the description is dropped AND a second bogus
        `$filter` property appears next to the real `filter` one, so the tool
        advertises two filters and documents neither.
        """
        params = self._cfg("list_annotations")["parameters"]
        assert "filter" in params
        assert "$filter" not in params

        by_name, _ = self._built()
        props = by_name["list_annotations"].inputSchema["properties"]
        assert "$filter" not in props
        assert "named parameters" in props["filter"]["description"]


@pytest.mark.unit
class TestToolsReturningWhatAPersonWrote:
    """A tool that hands back someone's words has to say not to invent them.

    Issue #2402: asked for the reviews on a test run, the Architect reported
    none of the real ones and wrote some of its own. Fabricated reviewer
    feedback is worse than an empty answer, because it is attributed to a
    named colleague and nothing in the reply marks it as invented.

    The prompt now forbids it, but the prompt is the Architect's alone. Any
    MCP client reads only the tool description, so the rule has to live there
    too. This is the check that the next such tool gets it: comments, tasks
    and tuning judgements are all the same shape, and whoever exposes one will
    not think of this bug.
    """

    # Tools whose response carries free text a person wrote, attributed to
    # them. Add to this when a new one is exposed rather than relaxing the
    # assertion -- the point is that the list grows with the surface.
    PERSON_AUTHORED: ClassVar[set[str]] = {"list_annotations", "get_annotation"}

    def _cfg(self, name):
        return {tc["name"]: tc for tc in load_tool_configs()}[name]

    @pytest.mark.parametrize("name", sorted(PERSON_AUTHORED))
    def test_the_description_forbids_reporting_what_was_not_returned(self, name):
        description = self._cfg(name)["description"]
        assert "never report an annotation that is not in the response" in description.replace(
            "\n", " "
        ).replace("  ", " "), f"{name} should forbid reporting rows it did not return"

    @pytest.mark.parametrize("name", sorted(PERSON_AUTHORED))
    def test_the_description_says_to_quote_rather_than_paraphrase(self, name):
        """A paraphrase puts words in a named person's mouth as surely as an
        invention does."""
        description = self._cfg(name)["description"].replace("\n", " ")
        assert "quote comments" in description
        assert "user.name" in description

    def test_the_list_tool_says_an_empty_result_is_the_answer(self):
        """The failure mode is a void being filled, so emptiness needs to read
        as a finding rather than as a gap."""
        description = self._cfg("list_annotations")["description"].replace("\n", " ")
        assert "empty result means nobody has annotated it" in description


@pytest.mark.unit
class TestEmptyListResponsesSayTheyAreEmpty:
    """The server side of the same problem.

    A bare [] is a void, and a model handed one tends to fill it. Every
    paginated tool gets a line saying the emptiness is the answer.
    """

    def _format(self, data, page_size=20, current_skip=0):
        from rhesis.backend.app.mcp_server.tools import format_list_response

        return format_list_response(data, page_size, current_skip)

    def test_an_empty_first_page_carries_a_hint(self):
        formatted = self._format([])

        assert formatted["results"] == []
        assert formatted["_pagination"]["returned"] == 0
        hint = formatted["_pagination"]["hint"]
        assert "No results matched" in hint
        assert "Do not describe results you did not receive" in hint

    def test_a_page_with_results_gets_no_empty_hint(self):
        formatted = self._format([{"id": "1"}])

        assert "hint" not in formatted["_pagination"]

    def test_an_empty_later_page_is_not_reported_as_nothing_found(self):
        """Paging past the end is exhaustion, not an absence of matches, and
        saying "none exist" there would contradict the rows already returned."""
        formatted = self._format([], current_skip=20)

        assert "hint" not in formatted["_pagination"]

    def test_a_full_page_still_advertises_the_next_one(self):
        formatted = self._format([{"id": str(i)} for i in range(21)], page_size=20)

        assert formatted["_pagination"]["has_more"] is True
        assert "next_skip" in formatted["_pagination"]


@pytest.mark.unit
class TestPublishedCatalogMatchesTheToolSurface:
    """skills/rhesis/references/tool-catalog.md ships as the agent's tool
    reference and nothing regenerates it from mcp_tools.yaml.

    The two directions of drift are not equally bad, but both are now closed,
    so both are enforced for every tool. A tool the catalog documents but the
    server does not expose sends an agent to call something that is not there;
    a tool the server exposes but the catalog omits is one the agent never
    learns it has.
    """

    @staticmethod
    def _documented():
        catalog = _REPO_ROOT / "skills/rhesis/references/tool-catalog.md"
        return set(re.findall(r"^### `([a-z_]+)`", catalog.read_text(), re.M))

    def test_the_catalog_names_no_tool_the_server_lacks(self):
        """The published skill told agents to call get_test_result_stats and
        get_test_run_stats long after both left the yaml."""
        phantom = self._documented() - {tc["name"] for tc in load_tool_configs()}
        assert not phantom, (
            f"tool-catalog.md documents tools the MCP server does not expose: {sorted(phantom)}"
        )

    def test_the_catalog_documents_every_tool_the_server_exposes(self):
        """The garak and owasp surfaces sat in the yaml undocumented, so an
        agent reading the skill had no way to know red-teaming was available."""
        missing = {tc["name"] for tc in load_tool_configs()} - self._documented()
        assert not missing, (
            f"tools missing from the published catalog: {sorted(missing)}"
        )


@pytest.mark.unit
class TestTraceTools:
    """Traces are the only view of what the application actually did.

    Before these tools existed the agent could read a result and the
    annotations on a trace, but could not open the trace itself. The two ids
    are what these tests guard hardest: the hex addresses the read route and
    the span row id addresses everything else, and confusing them fails
    quietly in one direction and loudly in the other.
    """

    TRACE_TOOLS: ClassVar[set[str]] = {
        "list_traces",
        "list_trace_providers",
        "get_trace",
        "get_trace_metrics",
        "lookup_span",
    }

    def _cfg(self, name):
        return {tc["name"]: tc for tc in load_tool_configs()}[name]

    def _built(self):
        from rhesis.backend.app.main import app
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        tools, operations = build_tools_and_operations(app)
        return {t.name: t for t in tools}, operations

    def test_trace_tools_in_yaml(self):
        names = {tc["name"] for tc in load_tool_configs()}
        missing = self.TRACE_TOOLS - names
        assert not missing, f"Missing trace tools: {sorted(missing)}"

    @pytest.mark.parametrize("name", sorted(TRACE_TOOLS))
    def test_the_tool_resolves_against_a_real_route(self, name):
        """A path that matches no OpenAPI route makes the tool vanish silently.

        The telemetry routes have no trailing slash, unlike /annotations/, so
        this is the check that catches a copied-in slash.
        """
        by_name, _ = self._built()
        assert name in by_name, f"{name} absent — path likely matches no route"

    @pytest.mark.parametrize("name", sorted(TRACE_TOOLS))
    def test_trace_tools_are_read_only(self, name):
        """Nothing here writes; ingestion is the SDK's job, not the agent's."""
        cfg = self._cfg(name)
        assert cfg["method"].upper() == "GET"
        assert "requires_confirmation" not in cfg
        by_name, _ = self._built()
        assert by_name[name].annotations.readOnlyHint is True

    def test_list_traces_does_not_declare_page_size(self):
        """page_size would mis-page this route rather than help it.

        The peek-ahead reads skip and sets limit, but this route pages by
        offset and answers with {traces, total, limit, offset} rather than a
        bare list. format_list_response no-ops on a dict, so the wrapper would
        add no metadata while next_skip advised a parameter the route ignores,
        leaving the agent re-reading page one.
        """
        assert "page_size" not in self._cfg("list_traces")

    def test_list_traces_caps_the_default_page(self):
        """Without this the route's own default of 100 traces comes back."""
        assert self._cfg("list_traces")["default_query"]["limit"] == 20

    def test_list_traces_tells_the_agent_to_page_by_offset(self):
        description = self._cfg("list_traces")["description"]
        assert "offset" in description
        assert "not skip" in description

    def test_the_route_really_has_no_skip(self):
        """Pins the claim rather than the prose making it.

        Every other list tool pages by skip, so "this one takes offset" is the
        kind of statement that quietly stops being true. If the route ever
        gains skip, this fails and the description gets revisited.
        """
        by_name, _ = self._built()
        props = by_name["list_traces"].inputSchema["properties"]
        assert "skip" not in props
        assert "offset" in props

    def test_list_traces_exposes_the_filters_that_matter(self):
        by_name, operations = self._built()
        props = by_name["list_traces"].inputSchema["properties"]
        for param in (
            "test_run_id",
            "test_result_id",
            "endpoint_id",
            "status_code",
            "span_name",
            "search",
            "duration_min_ms",
            "start_time_after",
            "trace_metrics_status",
            "root_spans_only",
            "offset",
        ):
            assert param in props, f"{param} missing from list_traces schema"
        assert operations["list_traces"]["method"] == "GET"

    def test_list_traces_documents_both_ids(self):
        """The listing carries only the hex, which is the trap."""
        description = self._cfg("list_traces")["description"]
        assert "root_spans[0].id" in description
        assert "32-char hex" in description

    def test_list_traces_explains_the_fail_closed_project_scope(self):
        """An empty list here usually means no project scope, not no traces.

        Without this the agent reports "there are no traces" to a user looking
        at a screen full of them.
        """
        description = self._cfg("list_traces")["description"]
        assert "project_id" in description
        assert "empty" in description.lower()

    def test_root_spans_only_explains_what_false_does(self):
        """Finding the failing operation needs the non-default value, so the
        doc has to say what it changes, not just that the flag exists."""
        doc = self._cfg("list_traces")["parameters"]["root_spans_only"]["description"]
        assert "every span" in doc
        assert "default" in doc

    def test_status_code_warns_it_matches_the_root_span(self):
        """A trace whose inner LLM call failed can have an OK root span."""
        doc = self._cfg("list_traces")["parameters"]["status_code"]["description"]
        assert "root" in doc
        assert "root_spans_only" in doc

    def test_get_trace_says_project_id_is_required(self):
        """The one read route in the API that will not infer the project."""
        cfg = self._cfg("get_trace")
        assert "REQUIRED" in cfg["parameters"]["project_id"]["description"]
        by_name, _ = self._built()
        assert "project_id" in by_name["get_trace"].inputSchema["required"]

    def test_get_trace_points_at_the_row_id(self):
        """This response is the only place the row id can be got."""
        description = self._cfg("get_trace")["description"]
        assert "root_spans[0].id" in description
        assert "create_annotation" in description

    def test_get_trace_warns_how_large_its_response_can_be(self):
        """Nothing truncates it, at any layer.

        The MCP server has no size cap, ingestion has no span cap, and a span
        carries up to 8000 characters of prompt and completion plus 10000 of
        conversation IO on the root. A twenty-span trace is tens of thousands
        of tokens, so the tool has to say so and name the cheaper call.
        """
        description = self._cfg("get_trace")["description"]
        assert "span_count" in description
        assert "root_spans_only=false" in description

    def test_list_traces_is_framed_as_diagnostic_not_routine(self):
        """Traces answer a question a result cannot; they are not a step in
        summarising a run. Without the NEVER an agent tends to open one per
        result while writing a pass-rate report, which costs context and tells
        the reader nothing they asked for."""
        description = self._cfg("list_traces")["description"]
        assert "diagnostic step, not part of routine analysis" in description
        assert "NEVER: open traces to build a run summary" in description

    def test_list_traces_says_why_it_is_the_cheap_call(self):
        """Its rows carry no attributes and no events, which is the whole
        reason the span listing is a usable substitute for the span tree."""
        description = self._cfg("list_traces")["description"]
        assert "no span attributes" in description
        assert "span_count" in description

    def test_the_listing_schema_really_carries_no_span_payload(self):
        """Pins the claim the guidance rests on.

        If TraceSummary ever gains attributes or events, the cheap path stops
        being cheap and every "use the listing instead" line above is wrong.
        """
        from rhesis.backend.app.schemas.telemetry import TraceSummary

        assert "attributes" not in TraceSummary.model_fields
        assert "events" not in TraceSummary.model_fields
        assert "span_count" in TraceSummary.model_fields

    def test_get_trace_metrics_says_get_insights_does_not_cover_traces(self):
        """Otherwise the obvious guess is that get_insights already does this."""
        description = self._cfg("get_trace_metrics")["description"]
        assert "get_insights" in description

    def test_get_trace_metrics_flags_unpriced_traces(self):
        """Reporting a partial cost as the total is the failure mode here."""
        description = self._cfg("get_trace_metrics")["description"]
        assert "priced_traces" in description

    def test_lookup_span_documents_the_way_back_from_an_annotation(self):
        description = self._cfg("lookup_span")["description"]
        assert "trace_db_id" in description
        assert "list_annotations" in description

    def test_create_annotation_says_a_trace_takes_the_row_id(self):
        """The whole point of the two-id warnings elsewhere: this call.

        Sending the hex as entity_id addresses no row, so the annotation
        cannot be created at all.
        """
        doc = self._cfg("create_annotation")["parameters"]["entity_id"]["description"]
        assert "Trace" in doc
        assert "root_spans[0].id" in doc
        assert "trace_db_id" in doc

    @pytest.mark.parametrize("name", sorted(TRACE_TOOLS))
    def test_the_published_catalog_documents_the_tool(self, name):
        """skills/rhesis/references/tool-catalog.md is hand-maintained.

        It ships to users as the agent's tool reference, and nothing regenerates
        it, so a tool added here and not there is invisible to every agent
        reading the skill.
        """
        catalog = _REPO_ROOT / "skills/rhesis/references/tool-catalog.md"
        assert f"### `{name}`" in catalog.read_text(), (
            f"{name} is in mcp_tools.yaml but not in the published tool catalog"
        )

    def test_search_warns_that_it_overrides_span_name(self):
        """crud/telemetry.py applies span_name in an `elif`, so passing both
        drops span_name with no error and returns a wider set than asked for."""
        doc = self._cfg("list_traces")["parameters"]["search"]["description"]
        assert "span_name" in doc
        assert "IGNORED" in doc or "ignored" in doc

    def test_search_documents_that_it_reaches_inner_spans(self):
        """It collects matching trace ids and returns whole traces, so it finds
        a trace whose child span carried the text even in the root-span view.
        That is what makes it the tool for an error message, where status_code
        only tests the row."""
        doc = self._cfg("list_traces")["parameters"]["search"]["description"]
        assert "every span" in doc
        assert "status_message" in doc

    def test_the_provider_filter_names_where_its_values_come_from(self):
        """A filter whose values cannot be discovered is the status_id trap.

        create_annotation once required a status_id that no tool exposed. An
        unmatched provider is worse than an error: the route accepts it and
        returns an empty page, which reads as "nothing used that provider"
        rather than as a typo.
        """
        doc = self._cfg("list_traces")["parameters"]["provider"]["description"]
        assert "list_trace_providers" in doc

    def test_list_trace_providers_explains_the_unknown_bucket(self):
        """ "unknown" is a real value, not a gap, and worth filtering to."""
        description = self._cfg("list_trace_providers")["description"]
        assert "unknown" in description

    def test_get_test_result_points_at_the_trace_for_why(self):
        """A result says what came back; only a trace says what happened."""
        description = self._cfg("get_test_result")["description"]
        assert "list_traces" in description
        assert "test_result_id" in description

    def test_list_annotations_says_how_to_open_the_trace(self):
        """It already warns which id links; reading one needs a second step."""
        description = self._cfg("list_annotations")["description"]
        assert "lookup_span" in description

    @pytest.mark.parametrize("name", ["get_trace", "get_trace_metrics"])
    def test_a_required_project_names_where_to_get_it(self, name):
        """These two are the only read routes that will not infer the project.

        Required and unguessable is a dead end unless the doc says which
        earlier tool result carries it, so the agent's alternative is asking
        the user for a UUID they do not have.
        """
        doc = self._cfg(name)["parameters"]["project_id"]["description"]
        assert "REQUIRED" in doc
        assert any(
            source in doc for source in ("list_traces", "context.project_id", "list_projects")
        ), f"{name} should name where project_id comes from"


@pytest.mark.unit
class TestGetTestResultDocumentsAnnotations:
    """A result carries its own annotation projections; the tool should say so."""

    def test_annotation_fields_are_documented(self):
        cfg = {tc["name"]: tc for tc in load_tool_configs()}["get_test_result"]
        for field in ("last_annotation", "matches_annotation", "annotation_summary"):
            assert field in cfg["description"], f"{field} undocumented"


@pytest.mark.unit
class TestCreateMetricDocumentsDescriptiveFields:
    """A metric the architect creates must be rich, not just scoreable.

    These fields exist on MetricCreate but carry no Pydantic descriptions,
    so the YAML overrides are the only thing telling the agent to fill
    them. Without them the agent sends name + evaluation_prompt only.
    """

    RICH_FIELDS = ("description", "evaluation_steps", "reasoning", "explanation")

    def _cfg(self):
        return {tc["name"]: tc for tc in load_tool_configs()}["create_metric"]

    def test_descriptive_fields_are_documented(self):
        params = self._cfg().get("parameters", {})
        missing = [f for f in self.RICH_FIELDS if f not in params]
        assert not missing, f"create_metric does not document: {missing}"

    def test_descriptive_field_docs_are_substantive(self):
        params = self._cfg()["parameters"]
        for field in self.RICH_FIELDS:
            text = (params[field] or {}).get("description", "")
            assert len(text.strip()) > 40, f"{field} needs a real description, got: {text!r}"

    def test_tool_description_demands_rich_metrics(self):
        description = self._cfg()["description"]
        for field in self.RICH_FIELDS:
            assert field in description, f"description should name {field}"

    def test_evaluation_steps_documents_the_stored_step_format(self):
        """Steps are split on '---' for display; a '1. 2. 3.' list renders as one step."""
        steps = self._cfg()["parameters"]["evaluation_steps"]["description"]
        assert "Step N:" in steps
        assert "---" in steps

    def test_evaluation_prompt_does_not_promise_placeholders(self):
        """Nothing substitutes {{response}} — the judge would see the literal braces."""
        prompt_doc = self._cfg()["parameters"]["evaluation_prompt"]["description"]
        assert "do NOT include placeholders" in prompt_doc

    def test_descriptive_fields_reach_the_tool_schema(self):
        from rhesis.backend.app.main import app
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        tools, _ = build_tools_and_operations(app)
        props = {t.name: t for t in tools}["create_metric"].inputSchema["properties"]
        for field in self.RICH_FIELDS:
            assert field in props, f"{field} absent from create_metric schema"
            assert props[field].get("description"), (
                f"{field} reached the schema with no description — the agent "
                "has no reason to fill it"
            )


@pytest.mark.unit
class TestMcpToolsYamlStructure:
    """Every tool entry must declare name, method, and path."""

    EXPECTED_NEW_PATHS: ClassVar[set[tuple[str, str, str]]] = {
        ("get_test_set", "GET", "/test_sets/{test_set_identifier}"),
        ("list_test_set_tests", "GET", "/test_sets/{test_set_identifier}/tests"),
        ("get_endpoint", "GET", "/endpoints/{endpoint_id}"),
        ("get_metric", "GET", "/metrics/{metric_id}"),
        ("create_source", "POST", "/sources/"),
        ("update_metric", "PUT", "/metrics/{metric_id}"),
        (
            "remove_requirement_from_metric",
            "DELETE",
            "/metrics/{metric_id}/requirements/{requirement_id}",
        ),
        ("update_test_set", "PUT", "/test_sets/{test_set_identifier}"),
        ("get_test", "GET", "/tests/{test_id}"),
        ("update_test", "PUT", "/tests/{test_id}"),
        ("get_requirement", "GET", "/requirements/{requirement_id}"),
        ("get_test_set_last_run", "GET", "/test_sets/{test_set_identifier}/last-run/{endpoint_id}"),
        ("get_test_set_metrics", "GET", "/test_sets/{test_set_identifier}/metrics"),
        ("get_project", "GET", "/projects/{project_id}"),
    }

    def test_all_entries_have_required_keys(self):
        for tc in load_tool_configs():
            assert tc.get("name")
            assert tc.get("method")
            assert tc.get("path", "").startswith("/")

    def test_new_tool_paths_configured(self):
        by_name = {tc["name"]: tc for tc in load_tool_configs()}
        for name, method, path in self.EXPECTED_NEW_PATHS:
            cfg = by_name[name]
            assert cfg["method"].upper() == method
            assert cfg["path"] == path


@pytest.mark.unit
class TestToolParameterDocumentation:
    """The rendered tool schema is the agent's only source of truth.

    An undescribed parameter is a field the model has to guess at, and a
    guess that misses costs a failed call plus a wasted ReAct iteration.
    """

    # The tools the Architect drives when it builds a suite. Failures here
    # are the ones users actually see, so these must be fully documented.
    # The rest of the catalog (update_*, endpoint config) still has gaps —
    # widen this set as they get cleaned up rather than relaxing the rule.
    CREATION_TOOLS: ClassVar[set[str]] = {
        "create_project",
        "create_requirement",
        "create_metric",
        "generate_metric",
        "improve_metric",
        "create_source",
        "add_requirement_to_metric",
        "create_test_set_bulk",
        "generate_test_set",
    }

    # Described by the OpenAPI schema itself, so a YAML override would only
    # duplicate them.
    EXEMPT: ClassVar[set[str]] = {"skip", "limit", "sort_by", "sort_order", "filter", "select"}

    # Mirrors _SERVER_MANAGED_FIELDS in rhesis.sdk.agents.base, which strips
    # these before the agent ever sees them. Duplicated rather than imported
    # so the backend suite does not depend on the SDK being installed, and
    # does not reach into a private name across package boundaries.
    SERVER_MANAGED: ClassVar[set[str]] = {
        "id",
        "nano_id",
        "user_id",
        "organization_id",
        "created_at",
        "updated_at",
        "owner_id",
        "assignee_id",
        "status_id",
        "model_id",
        "backend_type_id",
        "metric_type_id",
    }

    @staticmethod
    def _build_tools():
        from rhesis.backend.app.main import app
        from rhesis.backend.app.mcp_server.tools import build_tools_and_operations

        tools, operations = build_tools_and_operations(app)
        return {t.name: t for t in tools}, operations

    @staticmethod
    def _enum_values(prop):
        """Read enum values through the anyOf wrapper Optional[X] produces."""
        if "enum" in prop:
            return prop["enum"]
        for variant in prop.get("anyOf", []):
            if "enum" in variant:
                return variant["enum"]
        return None

    def test_creation_tool_parameters_are_described(self):
        by_name, _ = self._build_tools()
        undescribed = []
        for name in sorted(self.CREATION_TOOLS):
            schema = by_name[name].inputSchema or {}
            for param, prop in schema.get("properties", {}).items():
                if param in self.SERVER_MANAGED or param in self.EXEMPT:
                    continue
                if not prop.get("description"):
                    undescribed.append(f"{name}.{param}")

        assert not undescribed, (
            "Undescribed parameters on creation tools — the agent has to "
            "guess what to send. Add a description in mcp_tools.yaml: "
            f"{sorted(undescribed)}"
        )

    def test_required_fields_are_marked_in_schema(self):
        """Fields the route rejects when missing must say so in the schema.

        generate_test_set used to 400 on a missing name while declaring it
        optional, so the agent omitted it and ate a failure every time.
        """
        by_name, _ = self._build_tools()

        generate = by_name["generate_test_set"].inputSchema
        assert "config" in generate["required"]
        assert "name" in generate["required"]
        assert generate["properties"]["config"]["required"] == ["requirements"]

        bulk = by_name["create_test_set_bulk"].inputSchema
        assert "test_set_type" in bulk["required"]
        assert "tests" in bulk["required"]
        item_required = bulk["properties"]["tests"]["items"]["required"]
        assert {"requirement", "category", "topic"} <= set(item_required)

    def test_turn_type_fields_expose_their_allowed_values(self):
        """Bare `string` makes the model learn the two values from prose."""
        by_name, _ = self._build_tools()
        expected = ["Single-Turn", "Multi-Turn"]

        bulk = by_name["create_test_set_bulk"].inputSchema["properties"]
        assert self._enum_values(bulk["test_set_type"]) == expected
        item = bulk["tests"]["items"]["properties"]["test_type"]
        assert self._enum_values(item) == expected

        generate = by_name["generate_test_set"].inputSchema["properties"]
        assert self._enum_values(generate["test_type"]) == expected

    def test_project_id_is_not_required_for_generation(self):
        """It resolves from the request scope, so the agent need not send it."""
        by_name, _ = self._build_tools()
        generate = by_name["generate_test_set"].inputSchema
        assert "project_id" not in generate.get("required", [])
        assert generate["properties"]["project_id"].get("description")


@pytest.mark.unit
class TestProjectScopeGuidance:
    """Tool docs must not tell the agent to resolve or ask for a project.

    ``create_endpoint`` used to say ``project_id`` was REQUIRED and to
    "resolve it via list_projects (use the user's project, or ask if
    ambiguous)". Both are wrong: ``EndpointCreate.project_id`` is optional and
    ``auto_stamp`` fills it from the request scope. The agent followed the docs
    and asked the user which project they meant on every session.
    """

    _PROJECT_SCOPED_CREATES = ("create_endpoint", "create_project")

    def _tool(self, name):
        for tc in load_tool_configs():
            if tc["name"] == name:
                return tc
        pytest.fail(f"{name} missing from mcp_tools.yaml")

    @pytest.mark.parametrize("tool_name", _PROJECT_SCOPED_CREATES)
    def test_project_id_param_says_omit(self, tool_name):
        param = self._tool(tool_name)["parameters"]["project_id"]
        assert "Omit" in param["description"], (
            f"{tool_name} should tell the agent to omit project_id — the request scope supplies it"
        )

    @pytest.mark.parametrize("tool_name", _PROJECT_SCOPED_CREATES)
    def test_no_tool_asks_the_user_for_a_project(self, tool_name):
        tool = self._tool(tool_name)
        blob = " ".join(
            [tool.get("description", "")]
            + [p.get("description", "") for p in tool["parameters"].values()]
        )
        for banned in ("ask if ambiguous", "REQUIRED. UUID of the project"):
            assert banned not in blob, f"{tool_name} still says: {banned!r}"

    def test_create_endpoint_does_not_chain_through_list_projects(self):
        desc = self._tool("create_endpoint")["description"]
        assert "list_projects" not in desc, (
            "create_endpoint must not send the agent to list_projects — the "
            "endpoint lands in the request's project automatically"
        )

    def test_get_project_does_not_claim_create_endpoint_needs_it(self):
        desc = self._tool("get_project")["description"]
        assert "project_id\n      is required" not in desc
        assert "Not needed before create_endpoint" in desc.replace("\n      ", " ") or (
            "NOT needed before create_endpoint" in desc.replace("\n      ", " ")
        ), "get_project should say create_endpoint does not need it"
