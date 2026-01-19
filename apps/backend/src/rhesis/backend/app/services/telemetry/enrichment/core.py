"""Enrichment core functions.

Pure enrichment functions for calculating costs, detecting anomalies,
and extracting metadata from traces.
"""

import logging
from typing import Dict, List, Optional

import litellm

from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.schemas.enrichment import (
    Anomaly,
    CostBreakdown,
    TokenCosts,
)
from rhesis.backend.app.services.exchange_rate import get_usd_to_eur_rate
from rhesis.sdk.telemetry.attributes import AIAttributes
from rhesis.sdk.telemetry.schemas import StatusCode

logger = logging.getLogger(__name__)


def calculate_token_costs(spans: List[Trace]) -> Optional[TokenCosts]:
    """
    Calculate token costs for LLM spans using LiteLLM's pricing database.

    Costs are calculated in both USD and EUR for European operations.

    Args:
        spans: List of trace spans

    Returns:
        TokenCosts model with cost breakdown or None if no LLM spans
    """
    total_cost_usd = 0.0
    total_cost_eur = 0.0
    cost_breakdown = []

    # Get exchange rate for EUR conversion
    usd_to_eur = get_usd_to_eur_rate()

    logger.info(f"🔍 Calculating costs for {len(spans)} spans")

    for span in spans:
        # Only process LLM invocation spans (use semantic layer constant)
        operation_type = span.attributes.get(AIAttributes.OPERATION_TYPE)
        logger.debug(f"Span {span.span_id}: operation_type={operation_type}")

        if operation_type != AIAttributes.OPERATION_LLM_INVOKE:
            logger.debug(f"⏭️  Skipping span {span.span_id}: not an LLM invocation")
            continue

        model_name = span.attributes.get(AIAttributes.MODEL_NAME)
        logger.info(f"📊 Processing LLM span {span.span_id}: model={model_name}")

        if not model_name:
            logger.warning(f"⚠️  Skipping span {span.span_id}: no model name")
            continue

        # Get token counts (use semantic layer constants for token attributes)
        input_tokens = span.attributes.get(AIAttributes.LLM_TOKENS_INPUT, 0)
        output_tokens = span.attributes.get(AIAttributes.LLM_TOKENS_OUTPUT, 0)

        logger.info(f"🎯 Span {span.span_id} tokens: input={input_tokens}, output={output_tokens}")

        # Log all attributes for debugging
        if input_tokens == 0 and output_tokens == 0:
            logger.warning(
                f"⚠️  Zero tokens for span {span.span_id}! "
                f"Available attributes: {list(span.attributes.keys())}"
            )

        # Use LiteLLM's cost_per_token (maintains up-to-date pricing for all providers)
        try:
            # Returns tuple: (prompt_cost_usd, completion_cost_usd)
            input_cost_usd, output_cost_usd = litellm.cost_per_token(
                model=model_name,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )

            span_cost_usd = input_cost_usd + output_cost_usd

            # Convert to EUR
            span_cost_eur = span_cost_usd * usd_to_eur
            input_cost_eur = input_cost_usd * usd_to_eur
            output_cost_eur = output_cost_usd * usd_to_eur

            logger.info(
                f"💰 Calculated costs for {model_name}: "
                f"${span_cost_usd:.6f} USD, €{span_cost_eur:.6f} EUR"
            )

        except Exception as e:
            # If LiteLLM doesn't have pricing for this model, log and skip
            logger.warning(
                f"❌ LiteLLM cost calculation failed for model {model_name}: {e}. "
                f"Tokens: input={input_tokens}, output={output_tokens}"
            )
            continue

        total_cost_usd += span_cost_usd
        total_cost_eur += span_cost_eur

        # Create Pydantic model for breakdown
        cost_breakdown.append(
            CostBreakdown(
                span_id=span.span_id,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                input_cost_usd=round(input_cost_usd, 6),
                output_cost_usd=round(output_cost_usd, 6),
                total_cost_usd=round(span_cost_usd, 6),
                input_cost_eur=round(input_cost_eur, 6),
                output_cost_eur=round(output_cost_eur, 6),
                total_cost_eur=round(span_cost_eur, 6),
            )
        )

    if not cost_breakdown:
        logger.warning("⚠️  No cost breakdown calculated - no LLM spans with valid tokens found")
        return None

    logger.info(
        f"✅ Cost calculation complete: {len(cost_breakdown)} spans, "
        f"Total: ${total_cost_usd:.6f} USD / €{total_cost_eur:.6f} EUR"
    )

    return TokenCosts(
        total_cost_usd=round(total_cost_usd, 6),
        total_cost_eur=round(total_cost_eur, 6),
        breakdown=cost_breakdown,
    )


def detect_anomalies(spans: List[Trace]) -> Optional[List[Anomaly]]:
    """
    Detect anomalies in trace spans.

    Anomalies:
    - Slow spans (> 10 seconds)
    - High token usage (> 10,000 tokens)
    - Errors

    Args:
        spans: List of trace spans

    Returns:
        List of Anomaly models or None if none found
    """
    anomalies = []

    for span in spans:
        # Check for slow spans
        if span.duration_ms and span.duration_ms > 10000:  # 10 seconds
            anomalies.append(
                Anomaly(
                    type="slow_span",
                    span_id=span.span_id,
                    span_name=span.span_name,
                    duration_ms=span.duration_ms,
                    message=f"Span took {span.duration_ms / 1000:.1f}s (threshold: 10s)",
                )
            )

        # Check for high token usage (LLM spans only) - use semantic layer constants
        if span.attributes.get(AIAttributes.OPERATION_TYPE) == AIAttributes.OPERATION_LLM_INVOKE:
            total_tokens = span.attributes.get(AIAttributes.LLM_TOKENS_TOTAL, 0)
            if total_tokens > 10000:
                anomalies.append(
                    Anomaly(
                        type="high_token_usage",
                        span_id=span.span_id,
                        span_name=span.span_name,
                        total_tokens=total_tokens,
                        message=f"High token usage: {total_tokens} tokens (threshold: 10,000)",
                    )
                )

        # Check for errors - use semantic layer constant
        if span.status_code == StatusCode.ERROR.value:
            anomalies.append(
                Anomaly(
                    type="error",
                    span_id=span.span_id,
                    span_name=span.span_name,
                    error_message=span.status_message,
                    message=f"Span failed: {span.status_message or 'Unknown error'}",
                )
            )

    return anomalies if anomalies else None


def extract_metadata(spans: List[Trace]) -> Dict:
    """
    Extract useful metadata from trace spans.

    Args:
        spans: List of trace spans

    Returns:
        Dictionary of extracted metadata
    """
    metadata = {}

    # Collect unique models used
    models = set()
    tools = set()
    operation_types = set()

    for span in spans:
        # Extract operation type - use semantic layer constant
        op_type = span.attributes.get(AIAttributes.OPERATION_TYPE)
        if op_type:
            operation_types.add(op_type)

        # Extract model names - use semantic layer constant
        model_name = span.attributes.get(AIAttributes.MODEL_NAME)
        if model_name:
            models.add(model_name)

        # Extract tool names - use semantic layer constant
        tool_name = span.attributes.get(AIAttributes.TOOL_NAME)
        if tool_name:
            tools.add(tool_name)

    if models:
        metadata["models_used"] = list(models)

    if tools:
        metadata["tools_used"] = list(tools)

    if operation_types:
        metadata["operation_types"] = list(operation_types)

    # Extract root span name (often indicates the high-level operation)
    root_spans = [span for span in spans if span.parent_span_id is None]
    if root_spans:
        metadata["root_operation"] = root_spans[0].span_name

    return metadata
