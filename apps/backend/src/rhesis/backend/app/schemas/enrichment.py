"""Pydantic schemas for trace enrichment data."""

from typing import List, Optional

from pydantic import BaseModel, Field


class CostBreakdown(BaseModel):
    """Cost breakdown for a single span."""

    span_id: str = Field(..., description="Span ID")
    model_name: str = Field(..., description="Model name used")
    input_tokens: int = Field(..., ge=0, description="Number of input tokens")
    output_tokens: int = Field(..., ge=0, description="Number of output tokens")
    input_cost_usd: float = Field(..., ge=0, description="Cost of input tokens in USD")
    output_cost_usd: float = Field(..., ge=0, description="Cost of output tokens in USD")
    total_cost_usd: float = Field(..., ge=0, description="Total cost for this span in USD")
    input_cost_eur: float = Field(..., ge=0, description="Cost of input tokens in EUR")
    output_cost_eur: float = Field(..., ge=0, description="Cost of output tokens in EUR")
    total_cost_eur: float = Field(..., ge=0, description="Total cost for this span in EUR")


class TokenCosts(BaseModel):
    """Token costs for a trace."""

    total_cost_usd: float = Field(..., ge=0, description="Total cost across all spans in USD")
    total_cost_eur: float = Field(..., ge=0, description="Total cost across all spans in EUR")
    breakdown: List[CostBreakdown] = Field(..., description="Per-span cost breakdown")


class Anomaly(BaseModel):
    """Detected anomaly in a trace."""

    type: str = Field(..., description="Anomaly type (slow_span, high_token_usage, error)")
    span_id: str = Field(..., description="Span ID where anomaly was detected")
    span_name: str = Field(..., description="Span name")
    message: str = Field(..., description="Human-readable anomaly description")

    # Type-specific fields (optional)
    duration_ms: Optional[float] = Field(
        None, description="Duration in milliseconds (for slow_span)"
    )
    total_tokens: Optional[int] = Field(None, description="Token count (for high_token_usage)")
    error_message: Optional[str] = Field(None, description="Error message (for error)")


class TraceMetrics(BaseModel):
    """Trace-level metrics."""

    total_duration_ms: float = Field(..., ge=0, description="Total trace duration in milliseconds")
    span_count: int = Field(..., ge=1, description="Number of spans in trace")
    error_count: int = Field(..., ge=0, description="Number of error spans")


class EnrichedTraceData(BaseModel):
    """
    Enriched trace data structure.

    This is stored in the `enriched_data` JSONB field of the traces table.
    """

    costs: Optional[TokenCosts] = Field(None, description="Token costs (if LLM spans present)")
    anomalies: Optional[List[Anomaly]] = Field(None, description="Detected anomalies")
    metrics: TraceMetrics = Field(..., description="Trace-level metrics")

    # Metadata
    models_used: Optional[List[str]] = Field(None, description="List of models used in trace")
    tools_used: Optional[List[str]] = Field(None, description="List of tools invoked in trace")
    operation_types: Optional[List[str]] = Field(None, description="List of operation types")
    root_operation: Optional[str] = Field(None, description="Root span operation name")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "costs": {
                    "total_cost_usd": 0.006,
                    "total_cost_eur": 0.0055,
                    "breakdown": [
                        {
                            "span_id": "abc123",
                            "model_name": "gpt-4",
                            "input_tokens": 100,
                            "output_tokens": 50,
                            "input_cost_usd": 0.003,
                            "output_cost_usd": 0.003,
                            "total_cost_usd": 0.006,
                            "input_cost_eur": 0.00275,
                            "output_cost_eur": 0.00275,
                            "total_cost_eur": 0.0055,
                        }
                    ],
                },
                "anomalies": [
                    {
                        "type": "slow_span",
                        "span_id": "abc123",
                        "span_name": "ai.llm.invoke",
                        "duration_ms": 15000,
                        "message": "Span took 15.0s (threshold: 10s)",
                    }
                ],
                "metrics": {
                    "total_duration_ms": 2340.5,
                    "span_count": 3,
                    "error_count": 0,
                },
                "models_used": ["gpt-4"],
                "tools_used": ["search"],
                "operation_types": ["llm.invoke", "tool.invoke"],
                "root_operation": "ai.llm.invoke",
            }
        }
