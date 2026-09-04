"""Tests for trace enrichment functionality."""

from unittest.mock import Mock

import litellm
import pytest

# Import semantic layer constants
from rhesis.telemetry.attributes import AIAttributes

from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.schemas.enrichment import TokenCosts
from rhesis.backend.app.services.exchange_rate import get_usd_to_eur_rate
from rhesis.backend.app.services.telemetry.enrichment import (
    calculate_token_costs,
    detect_anomalies,
    extract_metadata,
)
from rhesis.backend.app.services.telemetry.enrichment.core import UNKNOWN_MODEL_NAME
from rhesis.backend.app.services.telemetry.enrichment.processor import TraceEnricher


class TestCalculateTokenCosts:
    """Test token cost calculation."""

    def test_calculate_costs_for_gpt4(self):
        """Test cost calculation for GPT-4 model using LiteLLM pricing in both USD and EUR."""
        input_tokens = 100
        output_tokens = 50
        model = "gpt-4"

        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: model,
                    AIAttributes.LLM_TOKENS_INPUT: input_tokens,
                    AIAttributes.LLM_TOKENS_OUTPUT: output_tokens,
                },
            )
        ]

        costs = calculate_token_costs(spans)

        # Calculate expected costs using LiteLLM
        input_cost_usd, output_cost_usd = litellm.cost_per_token(
            model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
        expected_cost_usd = input_cost_usd + output_cost_usd
        usd_to_eur = get_usd_to_eur_rate()
        expected_cost_eur = expected_cost_usd * usd_to_eur

        assert costs is not None
        assert isinstance(costs, TokenCosts)

        # Verify USD costs
        assert costs.total_cost_usd == pytest.approx(expected_cost_usd, rel=0.01)
        assert costs.breakdown[0].total_cost_usd == pytest.approx(expected_cost_usd, rel=0.01)

        # Verify EUR costs
        assert costs.total_cost_eur == pytest.approx(expected_cost_eur, rel=0.01)
        assert costs.breakdown[0].total_cost_eur == pytest.approx(expected_cost_eur, rel=0.01)

        # Verify metadata
        assert len(costs.breakdown) == 1
        assert costs.breakdown[0].span_id == "span1"
        assert costs.breakdown[0].model_name == model
        assert costs.breakdown[0].input_tokens == input_tokens
        assert costs.breakdown[0].output_tokens == output_tokens

    def test_calculate_costs_for_multiple_models(self):
        """Test cost calculation for multiple models using LiteLLM pricing in both currencies."""
        model1 = "gpt-4"
        input1, output1 = 100, 50
        model2 = "gpt-3.5-turbo"
        input2, output2 = 200, 100

        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: model1,
                    AIAttributes.LLM_TOKENS_INPUT: input1,
                    AIAttributes.LLM_TOKENS_OUTPUT: output1,
                },
            ),
            Mock(
                spec=Trace,
                span_id="span2",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: model2,
                    AIAttributes.LLM_TOKENS_INPUT: input2,
                    AIAttributes.LLM_TOKENS_OUTPUT: output2,
                },
            ),
        ]

        costs = calculate_token_costs(spans)

        # Calculate expected costs using LiteLLM
        input_cost1, output_cost1 = litellm.cost_per_token(
            model=model1, prompt_tokens=input1, completion_tokens=output1
        )
        input_cost2, output_cost2 = litellm.cost_per_token(
            model=model2, prompt_tokens=input2, completion_tokens=output2
        )
        expected_total_usd = input_cost1 + output_cost1 + input_cost2 + output_cost2

        usd_to_eur = get_usd_to_eur_rate()
        expected_total_eur = expected_total_usd * usd_to_eur

        assert costs is not None
        assert len(costs.breakdown) == 2
        assert costs.total_cost_usd == pytest.approx(expected_total_usd, rel=0.01)
        assert costs.total_cost_eur == pytest.approx(expected_total_eur, rel=0.01)

    def test_calculate_costs_no_llm_spans(self):
        """Test cost calculation returns None when no LLM spans present."""
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_TOOL_INVOKE,
                    AIAttributes.TOOL_NAME: "search",
                },
            )
        ]

        costs = calculate_token_costs(spans)

        assert costs is None

    def test_calculate_costs_unknown_model_keeps_tokens(self):
        """An unpriceable model still contributes its tokens, at zero cost.

        Tokens are known even when the price is not, so dropping the span would make
        a self-hosted or unrecognised model report zero usage.
        """
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: "unknown-model-xyz-123",
                    AIAttributes.LLM_TOKENS_INPUT: 100,
                    AIAttributes.LLM_TOKENS_OUTPUT: 50,
                    AIAttributes.LLM_TOKENS_TOTAL: 150,
                },
            )
        ]

        costs = calculate_token_costs(spans)

        assert costs is not None
        assert costs.total_cost_usd == 0.0
        assert costs.total_cost_eur == 0.0
        assert costs.total_input_tokens == 100
        assert costs.total_output_tokens == 50
        assert costs.total_tokens == 150

    def test_calculate_costs_mixed_priced_and_unpriced(self):
        """A trace mixing a priced and an unpriced model counts both models' tokens."""
        spans = [
            Mock(
                spec=Trace,
                span_id="priced",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: "gpt-4",
                    AIAttributes.LLM_TOKENS_INPUT: 100,
                    AIAttributes.LLM_TOKENS_OUTPUT: 50,
                    AIAttributes.LLM_TOKENS_TOTAL: 150,
                },
            ),
            Mock(
                spec=Trace,
                span_id="unpriced",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: "unknown-model-xyz-123",
                    AIAttributes.LLM_TOKENS_INPUT: 200,
                    AIAttributes.LLM_TOKENS_OUTPUT: 70,
                    AIAttributes.LLM_TOKENS_TOTAL: 270,
                },
            ),
        ]

        costs = calculate_token_costs(spans)

        assert costs is not None
        assert len(costs.breakdown) == 2
        assert costs.total_tokens == 420
        assert costs.total_input_tokens == 300
        assert costs.total_output_tokens == 120

        # Only the priced span carries cost; the unpriced one is recorded at zero.
        expected_usd = sum(
            litellm.cost_per_token(model="gpt-4", prompt_tokens=100, completion_tokens=50)
        )
        assert costs.total_cost_usd == pytest.approx(expected_usd, rel=0.01)
        unpriced = next(b for b in costs.breakdown if b.span_id == "unpriced")
        assert unpriced.total_cost_usd == 0.0
        assert unpriced.total_tokens == 270

    def test_calculate_costs_missing_model_name_keeps_tokens(self):
        """A span with no model name is recorded at zero cost rather than dropped."""
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.LLM_TOKENS_INPUT: 30,
                    AIAttributes.LLM_TOKENS_OUTPUT: 20,
                    AIAttributes.LLM_TOKENS_TOTAL: 50,
                },
            )
        ]

        costs = calculate_token_costs(spans)

        assert costs is not None
        assert costs.total_tokens == 50
        assert costs.total_cost_usd == 0.0
        assert costs.breakdown[0].model_name == UNKNOWN_MODEL_NAME

    def test_reported_total_is_trusted_not_derived(self):
        """Google ADK folds cache-read tokens into the reported total.

        Its ``ai.llm.tokens.total`` therefore exceeds ``input + output`` on purpose,
        and deriving the total would silently discard the cached tokens.
        """
        spans = [
            Mock(
                spec=Trace,
                span_id="adk-span",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: "gpt-4",
                    AIAttributes.LLM_TOKENS_INPUT: 100,
                    AIAttributes.LLM_TOKENS_OUTPUT: 50,
                    # 800 cache-read tokens folded in by google_adk/mapping.py
                    AIAttributes.LLM_TOKENS_TOTAL: 950,
                },
            )
        ]

        costs = calculate_token_costs(spans)

        assert costs is not None
        assert costs.total_tokens == 950
        assert costs.total_input_tokens == 100
        assert costs.total_output_tokens == 50

    def test_total_falls_back_to_sum_when_not_reported(self):
        """A span with no reported total derives one from input + output."""
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: "gpt-4",
                    AIAttributes.LLM_TOKENS_INPUT: 100,
                    AIAttributes.LLM_TOKENS_OUTPUT: 50,
                },
            )
        ]

        costs = calculate_token_costs(spans)

        assert costs is not None
        assert costs.total_tokens == 150

    def test_aggregated_agent_span_is_not_double_counted(self):
        """pydantic-ai reports usage twice; only the llm.invoke spans are counted.

        Its agent-run span carries the aggregate of its children's usage under the
        same ``ai.llm.tokens.*`` keys, so counting every span would roughly double
        the trace's real figure.
        """
        spans = [
            # Agent-run span carrying the aggregate of both model calls.
            Mock(
                spec=Trace,
                span_id="agent-run",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_AGENT_INVOKE,
                    AIAttributes.MODEL_NAME: "gpt-4",
                    AIAttributes.LLM_TOKENS_INPUT: 300,
                    AIAttributes.LLM_TOKENS_OUTPUT: 120,
                    AIAttributes.LLM_TOKENS_TOTAL: 420,
                },
            ),
            Mock(
                spec=Trace,
                span_id="model-call-1",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: "gpt-4",
                    AIAttributes.LLM_TOKENS_INPUT: 100,
                    AIAttributes.LLM_TOKENS_OUTPUT: 50,
                    AIAttributes.LLM_TOKENS_TOTAL: 150,
                },
            ),
            Mock(
                spec=Trace,
                span_id="model-call-2",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: "gpt-4",
                    AIAttributes.LLM_TOKENS_INPUT: 200,
                    AIAttributes.LLM_TOKENS_OUTPUT: 70,
                    AIAttributes.LLM_TOKENS_TOTAL: 270,
                },
            ),
        ]

        costs = calculate_token_costs(spans)

        assert costs is not None
        # The children sum to 420 -- the same figure the agent span reports. Counting
        # all three spans would give 840.
        assert costs.total_tokens == 420
        assert len(costs.breakdown) == 2

    def test_calculate_costs_model_variants(self):
        """Test that LiteLLM handles model variants (e.g., gpt-4-0613)."""
        model = "gpt-4-0613"
        input_tokens = 100
        output_tokens = 50

        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: model,
                    AIAttributes.LLM_TOKENS_INPUT: input_tokens,
                    AIAttributes.LLM_TOKENS_OUTPUT: output_tokens,
                },
            )
        ]

        costs = calculate_token_costs(spans)

        # LiteLLM knows about model variants
        input_cost, output_cost = litellm.cost_per_token(
            model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
        expected_cost = input_cost + output_cost

        assert costs is not None
        assert costs.total_cost_usd == pytest.approx(expected_cost, rel=0.01)

    def test_eur_conversion(self, mocker):
        """Test that EUR conversion uses the exchange rate from the service."""
        # Mock the exchange rate service to return a test rate
        mocker.patch(
            "rhesis.backend.app.services.telemetry.enrichment.core.get_usd_to_eur_rate",
            return_value=0.85,
        )

        model = "gpt-4"
        input_tokens = 100
        output_tokens = 50

        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: model,
                    AIAttributes.LLM_TOKENS_INPUT: input_tokens,
                    AIAttributes.LLM_TOKENS_OUTPUT: output_tokens,
                },
            )
        ]

        costs = calculate_token_costs(spans)

        # Verify the exchange rate was applied correctly
        input_cost_usd, output_cost_usd = litellm.cost_per_token(
            model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
        expected_cost_usd = input_cost_usd + output_cost_usd
        expected_cost_eur = expected_cost_usd * 0.85

        assert costs is not None
        assert costs.total_cost_usd == pytest.approx(expected_cost_usd, rel=0.01)
        assert costs.total_cost_eur == pytest.approx(expected_cost_eur, rel=0.01)

        # Verify breakdown also has correct EUR values
        assert costs.breakdown[0].total_cost_eur == pytest.approx(expected_cost_eur, rel=0.01)


class TestDetectAnomalies:
    """Test anomaly detection."""

    def test_detect_slow_span(self):
        """Test detection of slow spans."""
        spans = [
            Mock(
                spec=Trace,
                span_id="slow1",
                span_name="ai.llm.invoke",
                duration_ms=15000,  # 15 seconds (slow)
                status_code="OK",
                attributes={},
            ),
            Mock(
                spec=Trace,
                span_id="fast1",
                span_name="ai.tool.invoke",
                duration_ms=100,  # 100ms (fast)
                status_code="OK",
                attributes={},
            ),
        ]

        anomalies = detect_anomalies(spans)

        assert anomalies is not None
        assert len(anomalies) == 1
        assert anomalies[0].type == "slow_span"
        assert anomalies[0].span_id == "slow1"
        assert "15.0s" in anomalies[0].message

    def test_detect_high_token_usage(self):
        """Test detection of high token usage."""
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                span_name="ai.llm.invoke",
                duration_ms=1000,
                status_code="OK",
                attributes={
                    "ai.operation.type": "llm.invoke",
                    "ai.llm.tokens.total": 15000,  # High token count
                },
            )
        ]

        anomalies = detect_anomalies(spans)

        assert anomalies is not None
        assert len(anomalies) == 1
        assert anomalies[0].type == "high_token_usage"
        assert anomalies[0].total_tokens == 15000

    def test_detect_errors(self):
        """Test detection of error spans."""
        spans = [
            Mock(
                spec=Trace,
                span_id="error1",
                span_name="ai.llm.invoke",
                duration_ms=1000,
                status_code="ERROR",
                status_message="API timeout",
                attributes={},
            )
        ]

        anomalies = detect_anomalies(spans)

        assert anomalies is not None
        assert len(anomalies) == 1
        assert anomalies[0].type == "error"
        assert anomalies[0].error_message == "API timeout"

    def test_detect_multiple_anomalies(self):
        """Test detection of multiple anomaly types."""
        spans = [
            Mock(
                spec=Trace,
                span_id="slow_error",
                span_name="ai.llm.invoke",
                duration_ms=20000,  # Slow
                status_code="ERROR",  # Error
                status_message="Timeout",
                attributes={"ai.operation.type": "llm.invoke"},
            )
        ]

        anomalies = detect_anomalies(spans)

        assert anomalies is not None
        assert len(anomalies) == 2
        types = {a.type for a in anomalies}
        assert "slow_span" in types
        assert "error" in types

    def test_detect_no_anomalies(self):
        """Test that normal spans return None."""
        spans = [
            Mock(
                spec=Trace,
                span_id="normal",
                span_name="ai.llm.invoke",
                duration_ms=1000,
                status_code="OK",
                attributes={
                    "ai.operation.type": "llm.invoke",
                    "ai.llm.tokens.total": 500,
                },
            )
        ]

        anomalies = detect_anomalies(spans)

        assert anomalies is None


class TestExtractMetadata:
    """Test metadata extraction."""

    def test_extract_models_used(self):
        """Test extraction of models used."""
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                span_name="ai.llm.invoke",
                parent_span_id=None,
                attributes={
                    "ai.operation.type": "llm.invoke",
                    "ai.model.name": "gpt-4",
                },
            ),
            Mock(
                spec=Trace,
                span_id="span2",
                span_name="ai.llm.invoke",
                parent_span_id="span1",
                attributes={
                    "ai.operation.type": "llm.invoke",
                    "ai.model.name": "gpt-3.5-turbo",
                },
            ),
        ]

        metadata = extract_metadata(spans)

        assert "models_used" in metadata
        assert set(metadata["models_used"]) == {"gpt-4", "gpt-3.5-turbo"}

    def test_extract_tools_used(self):
        """Test extraction of tools used."""
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                span_name="ai.tool.invoke",
                parent_span_id=None,
                attributes={
                    "ai.operation.type": "tool.invoke",
                    "ai.tool.name": "search",
                },
            ),
            Mock(
                spec=Trace,
                span_id="span2",
                span_name="ai.tool.invoke",
                parent_span_id="span1",
                attributes={
                    "ai.operation.type": "tool.invoke",
                    "ai.tool.name": "calculator",
                },
            ),
        ]

        metadata = extract_metadata(spans)

        assert "tools_used" in metadata
        assert set(metadata["tools_used"]) == {"search", "calculator"}

    def test_extract_operation_types(self):
        """Test extraction of operation types."""
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                span_name="ai.llm.invoke",
                parent_span_id=None,
                attributes={"ai.operation.type": "llm.invoke"},
            ),
            Mock(
                spec=Trace,
                span_id="span2",
                span_name="ai.tool.invoke",
                parent_span_id="span1",
                attributes={"ai.operation.type": "tool.invoke"},
            ),
        ]

        metadata = extract_metadata(spans)

        assert "operation_types" in metadata
        assert set(metadata["operation_types"]) == {"llm.invoke", "tool.invoke"}

    def test_extract_root_operation(self):
        """Test extraction of root operation name."""
        spans = [
            Mock(
                spec=Trace,
                span_id="root",
                span_name="ai.llm.invoke",
                parent_span_id=None,  # Root span
                attributes={},
            ),
            Mock(
                spec=Trace,
                span_id="child",
                span_name="ai.tool.invoke",
                parent_span_id="root",
                attributes={},
            ),
        ]

        metadata = extract_metadata(spans)

        assert "root_operation" in metadata
        assert metadata["root_operation"] == "ai.llm.invoke"

    def test_extract_empty_metadata(self):
        """Test extraction returns empty dict when no metadata."""
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                span_name="unknown",
                parent_span_id="parent",
                attributes={},
            )
        ]

        metadata = extract_metadata(spans)

        assert isinstance(metadata, dict)
        assert len(metadata) == 0


class TestTraceEnricher:
    """Test TraceEnricher service."""

    def test_enrich_trace_with_cache_hit(self, mocker):
        """Test enrichment uses cached data when available."""
        # Mock database session
        mock_db = Mock()

        # Mock span with cached enrichment (valid EnrichedTraceData dict)
        mock_span = Mock(
            spec=Trace,
            enriched_data={
                "costs": {
                    "total_cost_usd": 0.01,
                    "total_cost_eur": 0.0092,
                    "breakdown": [],
                },
                "metrics": {
                    "total_duration_ms": 1000.0,
                    "span_count": 1,
                    "error_count": 0,
                },
            },
        )

        # Mock get_trace_by_id to return span with cached data
        mock_get_trace = mocker.patch(
            "rhesis.backend.app.services.telemetry.enrichment.processor.get_trace_by_id",
            return_value=[mock_span],
        )

        enricher = TraceEnricher(mock_db)
        result = enricher.enrich_trace("trace123", "project123", "org123")

        # Should return EnrichedTraceData model (converted from cached dict)
        from rhesis.backend.app.schemas.enrichment import EnrichedTraceData

        assert isinstance(result, EnrichedTraceData)
        assert result.costs is not None
        assert result.metrics is not None
        assert result.metrics.span_count == 1

        # Verify organization_id was passed to get_trace_by_id
        mock_get_trace.assert_called_once_with(
            mock_db, trace_id="trace123", project_id="project123", organization_id="org123"
        )

    def test_enrich_trace_calculates_when_no_cache(self, mocker):
        """Test enrichment calculates data when no cache exists."""
        mock_db = Mock()

        # Mock span without enriched data
        mock_span = Mock(
            spec=Trace,
            span_id="span1",
            span_name="ai.llm.invoke",
            duration_ms=1000,
            status_code="OK",
            parent_span_id=None,
            enriched_data=None,  # No cache
            attributes={
                AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                AIAttributes.MODEL_NAME: "gpt-4",
                AIAttributes.LLM_TOKENS_INPUT: 100,
                AIAttributes.LLM_TOKENS_OUTPUT: 50,
            },
        )

        # Mock get_trace_by_id
        mock_get_trace = mocker.patch(
            "rhesis.backend.app.services.telemetry.enrichment.processor.get_trace_by_id",
            return_value=[mock_span],
        )

        # Mock mark_trace_processed
        mock_mark = mocker.patch(
            "rhesis.backend.app.services.telemetry.enrichment.processor.mark_trace_processed"
        )

        enricher = TraceEnricher(mock_db)
        result = enricher.enrich_trace("trace123", "project123", "org123")

        # Should calculate enrichment (returns EnrichedTraceData model)
        assert result.costs is not None
        assert result.metrics is not None
        assert result.metrics.span_count == 1

        # Should cache the result (as dict in database)
        mock_mark.assert_called_once()

        # Verify organization_id was passed to get_trace_by_id
        mock_get_trace.assert_called_once_with(
            mock_db, trace_id="trace123", project_id="project123", organization_id="org123"
        )

    def test_enrich_trace_no_spans(self, mocker):
        """Test enrichment returns None when no spans found."""
        mock_db = Mock()

        # Mock get_trace_by_id to return empty list
        mock_get_trace = mocker.patch(
            "rhesis.backend.app.services.telemetry.enrichment.processor.get_trace_by_id", return_value=[]
        )

        enricher = TraceEnricher(mock_db)
        result = enricher.enrich_trace("trace123", "project123", "org123")

        assert result is None

        # Verify organization_id was passed to get_trace_by_id
        mock_get_trace.assert_called_once_with(
            mock_db, trace_id="trace123", project_id="project123", organization_id="org123"
        )

    def test_calculate_enrichment_combines_all_data(self, mocker):
        """Test that _calculate_enrichment combines costs, anomalies, and metadata."""
        mock_db = Mock()
        enricher = TraceEnricher(mock_db)

        # Create realistic mock spans
        spans = [
            Mock(
                spec=Trace,
                span_id="span1",
                span_name="ai.llm.invoke",
                duration_ms=1000,
                status_code="OK",
                parent_span_id=None,
                attributes={
                    AIAttributes.OPERATION_TYPE: AIAttributes.OPERATION_LLM_INVOKE,
                    AIAttributes.MODEL_NAME: "gpt-4",
                    AIAttributes.LLM_TOKENS_INPUT: 100,
                    AIAttributes.LLM_TOKENS_OUTPUT: 50,
                },
            )
        ]

        result = enricher._calculate_enrichment(spans)

        # Should include costs (from LLM span) - returns EnrichedTraceData model
        assert result.costs is not None
        assert result.costs.total_cost_usd > 0

        # Should include metrics
        assert result.metrics is not None
        assert result.metrics.span_count == 1
        assert result.metrics.error_count == 0

        # Should include metadata
        assert result.models_used is not None
        assert "gpt-4" in result.models_used
