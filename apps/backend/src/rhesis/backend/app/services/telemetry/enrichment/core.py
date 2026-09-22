"""Enrichment core functions.

Pure enrichment functions for calculating costs, detecting anomalies,
and extracting metadata from traces.
"""

import logging
from typing import Dict, List, Optional

import litellm
from rhesis.telemetry.attributes import AIAttributes
from rhesis.telemetry.schemas import StatusCode

from rhesis.backend.app.models.trace import Trace
from rhesis.backend.app.schemas.enrichment import (
    Anomaly,
    CostBreakdown,
    TokenCosts,
)
from rhesis.backend.app.services.exchange_rate import get_usd_to_eur_rate
from rhesis.backend.app.services.telemetry.providers import resolve_provider

litellm.suppress_debug_info = True
for _logger_name in ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy"):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Stands in for a missing ai.llm.model.name so the span's tokens still get recorded.
UNKNOWN_MODEL_NAME = "unknown"


def _span_token_counts(span: Trace) -> tuple[int, int, int]:
    """Input, output and total tokens for a span.

    The reported total is trusted rather than derived: Google ADK folds cache-read
    tokens into ``ai.llm.tokens.total``, so for its spans the total legitimately
    exceeds ``input + output``. Fall back to the sum when no total was sent, and also
    when a zero total arrives alongside non-zero input or output, which is
    contradictory and only reachable through hand-set attributes.
    """
    input_tokens = int(span.attributes.get(AIAttributes.LLM_TOKENS_INPUT, 0) or 0)
    output_tokens = int(span.attributes.get(AIAttributes.LLM_TOKENS_OUTPUT, 0) or 0)
    reported_total = span.attributes.get(AIAttributes.LLM_TOKENS_TOTAL)
    if reported_total is None or int(reported_total) == 0:
        return input_tokens, output_tokens, input_tokens + output_tokens
    return input_tokens, output_tokens, int(reported_total)


def _price_span(span: Trace, usd_to_eur: float) -> CostBreakdown:
    """Price a single ``llm.invoke`` span.

    Always returns a breakdown: tokens are known even when the price is not, so an
    unpriced model (self-hosted, or missing from LiteLLM) keeps its tokens and its
    model name rather than being dropped. Dropping it would make a trace that mixes
    priced and unpriced spans undercount its tokens.

    Its costs come back as ``None``, not zero, whenever the span cannot be priced.
    Zero is what a genuinely free model costs, and a reader who cannot tell the two
    apart reads an unpriceable run as a free one. Three things stop a span being
    priced: no model name, a model LiteLLM has no rate for, and no tokens to price.
    """
    input_tokens, output_tokens, total_tokens = _span_token_counts(span)
    model_name = span.attributes.get(AIAttributes.MODEL_NAME)
    provider = resolve_provider(span.attributes, model_name)

    input_cost_usd: Optional[float] = None
    output_cost_usd: Optional[float] = None

    if not model_name:
        logger.warning(f"⚠️  Span {span.span_id} has no model name: recording tokens without a cost")
        model_name = UNKNOWN_MODEL_NAME
    elif input_tokens == 0 and output_tokens == 0:
        # Pricing this anyway is the trap. LiteLLM happily returns 0.0 for zero tokens,
        # which lands on screen as a run that cost nothing rather than one we could not
        # read, and an llm.invoke span with no tokens almost always means we failed to
        # parse the provider's reply.
        logger.warning(
            f"⚠️  Zero tokens for span {span.span_id}: recording no cost. "
            f"Available attributes: {list(span.attributes.keys())}"
        )
    else:
        try:
            # Returns tuple: (prompt_cost_usd, completion_cost_usd)
            input_cost_usd, output_cost_usd = litellm.cost_per_token(
                model=model_name,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
            )
        except Exception as e:
            logger.warning(
                f"❌ LiteLLM cost calculation failed for model {model_name}: {e}. "
                f"Recording tokens without a cost: input={input_tokens}, output={output_tokens}"
            )

    priced = input_cost_usd is not None and output_cost_usd is not None
    span_cost_usd = (input_cost_usd or 0.0) + (output_cost_usd or 0.0) if priced else None

    def usd(value: Optional[float]) -> Optional[float]:
        return None if value is None else round(value, 6)

    def eur(value: Optional[float]) -> Optional[float]:
        return None if value is None else round(value * usd_to_eur, 6)

    return CostBreakdown(
        span_id=span.span_id,
        model_name=model_name,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_cost_usd=usd(input_cost_usd),
        output_cost_usd=usd(output_cost_usd),
        total_cost_usd=usd(span_cost_usd),
        input_cost_eur=eur(input_cost_usd),
        output_cost_eur=eur(output_cost_usd),
        total_cost_eur=eur(span_cost_usd),
    )


def calculate_token_costs(spans: List[Trace]) -> Optional[TokenCosts]:
    """
    Calculate token counts and costs for LLM spans using LiteLLM's pricing database.

    Only ``llm.invoke`` spans are counted. That filter is what keeps the totals
    correct: frameworks like pydantic-ai report aggregated usage on the agent-run
    span *and* per-call usage on its child model-call spans, so summing every span
    would double-count them.

    Costs are calculated in both USD and EUR for European operations. A span LiteLLM
    cannot price keeps its tokens and its model name but carries no cost, and the
    totals here follow suit: they are ``None`` when nothing on the trace could be
    priced, rather than zero.

    Args:
        spans: List of trace spans

    Returns:
        TokenCosts model with token totals and cost breakdown, or None if the trace
        has no LLM invocation spans at all.
    """
    usd_to_eur = get_usd_to_eur_rate()

    logger.info(f"🔍 Calculating costs for {len(spans)} spans")

    cost_breakdown = [
        _price_span(span, usd_to_eur)
        for span in spans
        if span.attributes.get(AIAttributes.OPERATION_TYPE) == AIAttributes.OPERATION_LLM_INVOKE
    ]

    if not cost_breakdown:
        logger.warning("⚠️  No cost breakdown calculated - trace has no llm.invoke spans")
        return None

    def total(field: str) -> Optional[float]:
        """Sum one cost field across the spans that carry it.

        ``None`` when not one of them carries it, which is how a trace nothing could
        price stays distinguishable from a trace priced at nothing. A trace that mixes
        the two sums the priced half, since those tokens really did cost that much.
        """
        priced = [value for entry in cost_breakdown if (value := getattr(entry, field)) is not None]
        return round(sum(priced), 6) if priced else None

    total_cost_usd = total("total_cost_usd")
    total_cost_eur = total("total_cost_eur")

    if total_cost_usd is None:
        logger.warning(
            f"⚠️  Cost calculation complete: {len(cost_breakdown)} spans, "
            "none of which could be priced"
        )
    else:
        logger.info(
            f"✅ Cost calculation complete: {len(cost_breakdown)} spans, "
            f"Total: ${total_cost_usd:.6f} USD / €{total_cost_eur:.6f} EUR"
        )

    return TokenCosts(
        total_cost_usd=total_cost_usd,
        total_cost_eur=total_cost_eur,
        total_input_cost_usd=total("input_cost_usd"),
        total_output_cost_usd=total("output_cost_usd"),
        total_input_tokens=sum(entry.input_tokens for entry in cost_breakdown),
        total_output_tokens=sum(entry.output_tokens for entry in cost_breakdown),
        total_tokens=sum(entry.total_tokens for entry in cost_breakdown),
        # dict.fromkeys dedupes while keeping first-seen order, so the lists are stable
        # between runs over the same trace.
        models_used=list(dict.fromkeys(e.model_name for e in cost_breakdown if e.model_name)),
        providers_used=list(dict.fromkeys(e.provider for e in cost_breakdown if e.provider)),
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
