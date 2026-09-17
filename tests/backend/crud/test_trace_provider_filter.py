"""Tests for filtering traces by LLM provider, and for the list behind the checklist.

The provider is not a column and usually not recorded anywhere: most breakdown entries
predate the field and are placed from their model name through LiteLLM, which SQL cannot
call. The filter therefore resolves the scope's pairs in Python and turns the answer back
into a clause, and the thing it must never do is disagree with the Model column beside it.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import SpanKind, StatusCode

from rhesis.backend.app.crud.telemetry import (
    create_trace_spans,
    list_trace_providers,
    mark_trace_processed,
    query_traces,
)
from rhesis.backend.app.schemas.telemetry import OTELSpanCreate
from rhesis.backend.app.services.telemetry.token_totals import trace_summary_usage


def root_span(trace_id, project_id, *, stamped_provider=None, model=None):
    now = datetime.now(timezone.utc)
    attributes = {AIAttributes.OPERATION_TYPE: "llm.invoke"}
    if model:
        attributes[AIAttributes.MODEL_NAME] = model
    if stamped_provider:
        attributes[AIAttributes.MODEL_PROVIDER] = stamped_provider
    return OTELSpanCreate(
        trace_id=trace_id,
        span_id=uuid.uuid4().hex[:16],
        parent_span_id=None,
        project_id=project_id,
        environment="development",
        span_name="ai.llm.invoke",
        span_kind=SpanKind.CLIENT,
        start_time=now,
        end_time=now + timedelta(seconds=1),
        status_code=StatusCode.OK,
        attributes=attributes,
    )


def blob(*models_and_providers):
    """A breakdown. A provider of None is the legacy shape: recorded nowhere."""
    return {
        "costs": {
            "total_cost_usd": 0.03,
            "breakdown": [
                {
                    "span_id": uuid.uuid4().hex[:16],
                    "model_name": model,
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                    "input_cost_usd": 0.02,
                    "output_cost_usd": 0.01,
                    "total_cost_usd": 0.03,
                    **({"provider": provider} if provider else {}),
                }
                for model, provider in models_and_providers
            ],
        }
    }


def traced(db, project_id, org_id, *, enrichment=None, stamped=None, model=None):
    trace_id = uuid.uuid4().hex
    create_trace_spans(
        db,
        [root_span(trace_id, project_id, stamped_provider=stamped, model=model)],
        organization_id=org_id,
    )
    if enrichment is not None:
        mark_trace_processed(db, trace_id, enrichment)
    return trace_id


@pytest.fixture
def mixed_traces(test_db, db_project, test_org_id):
    """One trace per provider, one using two, and one nothing has priced."""
    project_id = str(db_project.id)
    return project_id, {
        "openai": traced(test_db, project_id, test_org_id, enrichment=blob(("gpt-4", None))),
        "gemini": traced(
            test_db, project_id, test_org_id, enrichment=blob(("gemini-2.0-flash", None))
        ),
        "both": traced(
            test_db,
            project_id,
            test_org_id,
            enrichment=blob(("gpt-4", None), ("gemini-2.0-flash", None)),
        ),
        "unenriched": traced(test_db, project_id, test_org_id, model="gpt-4"),
    }


def filtered(db, org_id, project_id, providers):
    rows = query_traces(
        db, organization_id=org_id, project_id=project_id, providers=providers, limit=100
    )
    return {row.trace.trace_id for row in rows}


@pytest.mark.integration
class TestProviderFilter:
    def test_narrows_to_one_provider(self, test_db, test_org_id, mixed_traces):
        project_id, traces = mixed_traces

        matched = filtered(test_db, test_org_id, project_id, ["openai"])

        assert traces["openai"] in matched
        assert traces["both"] in matched
        assert traces["gemini"] not in matched

    def test_several_providers_are_a_union(self, test_db, test_org_id, mixed_traces):
        """A checklist, not a radio button: ticking two widens rather than narrows."""
        project_id, traces = mixed_traces

        matched = filtered(test_db, test_org_id, project_id, ["openai", "gemini"])

        assert {traces["openai"], traces["gemini"], traces["both"]} <= matched

    def test_a_trace_using_both_matches_either(self, test_db, test_org_id, mixed_traces):
        project_id, traces = mixed_traces

        assert traces["both"] in filtered(test_db, test_org_id, project_id, ["openai"])
        assert traces["both"] in filtered(test_db, test_org_id, project_id, ["gemini"])

    def test_no_providers_is_no_filter(self, test_db, test_org_id, mixed_traces):
        project_id, traces = mixed_traces

        matched = filtered(test_db, test_org_id, project_id, None)

        assert traces["unenriched"] in matched

    def test_an_unknown_provider_matches_nothing(self, test_db, test_org_id, mixed_traces):
        project_id, _ = mixed_traces

        assert filtered(test_db, test_org_id, project_id, ["not-a-provider"]) == set()

    def test_an_alias_resolves_to_the_same_traces(self, test_db, test_org_id, mixed_traces):
        """LiteLLM calls a bare gemini model vertex_ai; the filter folds them together."""
        project_id, _ = mixed_traces

        assert filtered(test_db, test_org_id, project_id, ["vertex_ai"]) == filtered(
            test_db, test_org_id, project_id, ["gemini"]
        )

    def test_an_unenriched_trace_matches_no_provider(self, test_db, test_org_id, mixed_traces):
        """Its Model column is a dash, so it must not answer a provider filter either."""
        project_id, traces = mixed_traces

        matched = filtered(test_db, test_org_id, project_id, ["openai", "gemini"])

        assert traces["unenriched"] not in matched

    def test_a_recorded_provider_beats_what_the_model_implies(
        self, test_db, db_project, test_org_id
    ):
        """An entry recorded as azure is azure, whatever its model name suggests."""
        project_id = str(db_project.id)
        azure = traced(test_db, project_id, test_org_id, enrichment=blob(("gpt-4", "azure")))

        assert azure in filtered(test_db, test_org_id, project_id, ["azure"])
        assert azure not in filtered(test_db, test_org_id, project_id, ["openai"])


@pytest.mark.integration
class TestFilterAgreesWithTheRow:
    """Whatever comes back must display the provider that was asked for."""

    def test_every_matched_trace_shows_that_provider(self, test_db, test_org_id, mixed_traces):
        project_id, _ = mixed_traces

        for provider in ("openai", "gemini"):
            rows = query_traces(
                test_db,
                organization_id=test_org_id,
                project_id=project_id,
                providers=[provider],
                limit=100,
            )
            for row in rows:
                shown = trace_summary_usage(row.trace.enriched_data, row.llm_tokens)["providers"]
                assert provider in shown, f"{provider} filter returned a row showing {shown}"

    def test_the_stamped_attribute_does_not_leak_in(self, test_db, db_project, test_org_id):
        """The span says openai, the breakdown says nothing, so the row shows gemini.

        Filtering the span attributes instead of the breakdown returned this trace for
        openai while its Model column read gemini. Real data on the dev instance has
        exactly this shape.
        """
        project_id = str(db_project.id)
        trace_id = uuid.uuid4().hex
        create_trace_spans(
            test_db,
            [root_span(trace_id, project_id, stamped_provider="openai", model="gemini-2.0-flash")],
            organization_id=test_org_id,
        )
        mark_trace_processed(test_db, trace_id, blob(("gemini-2.0-flash", None)))

        assert trace_id not in filtered(test_db, test_org_id, project_id, ["openai"])
        assert trace_id in filtered(test_db, test_org_id, project_id, ["gemini"])


@pytest.mark.integration
class TestProviderList:
    """What the checklist offers."""

    def test_lists_every_provider_in_scope(self, test_db, test_org_id, mixed_traces):
        project_id, _ = mixed_traces

        assert list_trace_providers(test_db, test_org_id, project_id) == ["gemini", "openai"]

    def test_offers_nothing_that_would_return_nothing(self, test_db, test_org_id, mixed_traces):
        """Every option must match at least one trace, or the checklist lies."""
        project_id, _ = mixed_traces

        for provider in list_trace_providers(test_db, test_org_id, project_id):
            assert filtered(test_db, test_org_id, project_id, [provider])

    def test_a_project_with_nothing_priced_offers_nothing(self, test_db, db_project, test_org_id):
        project_id = str(db_project.id)
        traced(test_db, project_id, test_org_id, model="gpt-4")

        assert list_trace_providers(test_db, test_org_id, project_id) == []

    def test_an_unplaceable_model_is_offered_as_unknown(self, test_db, db_project, test_org_id):
        """Those traces exist, and filtering to them is how you find what is unattributed."""
        project_id = str(db_project.id)
        trace_id = traced(
            test_db, project_id, test_org_id, enrichment=blob(("self-hosted-7b", None))
        )

        assert list_trace_providers(test_db, test_org_id, project_id) == ["unknown"]
        assert trace_id in filtered(test_db, test_org_id, project_id, ["unknown"])
