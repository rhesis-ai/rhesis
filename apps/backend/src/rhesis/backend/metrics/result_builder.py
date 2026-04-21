"""
Result builder for metric evaluation output.

Provides a single schema and factory methods for success, error, and timeout
results produced by MetricEvaluator, replacing ad-hoc dict construction.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Union


@dataclass
class MetricResultBuilder:
    """Standard shape for metric evaluation results.

    Provides factory classmethods for success, error, and timeout
    results. Call .to_dict() to get the plain dict for storage.
    """

    score: Optional[Union[float, str]]
    reason: str
    is_successful: Optional[bool]
    backend: str
    name: str
    class_name: str
    description: str = ""
    threshold: Optional[float] = None
    reference_score: Optional[Union[float, str]] = None
    error_message: Optional[str] = None  # output key "error" for API
    error_type: Optional[str] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict, omitting None optional fields except core result fields."""
        _always_include = {"score", "is_successful"}
        d = {k: v for k, v in asdict(self).items() if v is not None or k in _always_include}
        if "error_message" in d:
            d["error"] = d.pop("error_message")
        return d

    @classmethod
    def success(
        cls,
        *,
        score: Optional[Union[float, str]],
        reason: str,
        is_successful: Optional[bool],
        backend: str,
        name: str,
        class_name: str,
        description: str = "",
        threshold: Optional[float] = None,
        reference_score: Optional[Union[float, str]] = None,
        duration_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Build a success result dict."""
        return cls(
            score=score,
            reason=reason,
            is_successful=is_successful,
            backend=backend,
            name=name,
            class_name=class_name,
            description=description,
            threshold=threshold,
            reference_score=reference_score,
            duration_ms=duration_ms,
        ).to_dict()

    @classmethod
    def error(
        cls,
        *,
        reason: str,
        backend: str,
        name: str,
        class_name: str,
        description: str = "",
        error: Optional[str] = None,
        error_type: Optional[str] = None,
        threshold: Optional[float] = None,
        reference_score: Optional[Union[float, str]] = None,
        duration_ms: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Build an error result dict (score=0.0, is_successful=False)."""
        return cls(
            score=0.0,
            reason=reason,
            is_successful=False,
            backend=backend,
            name=name,
            class_name=class_name,
            description=description,
            threshold=threshold,
            reference_score=reference_score,
            error_message=error,
            error_type=error_type,
            duration_ms=duration_ms,
        ).to_dict()

    @classmethod
    def timeout(
        cls,
        *,
        backend: str,
        name: str,
        class_name: str,
        description: str = "",
        threshold: Optional[float] = None,
        timeout_seconds: int = 600,
    ) -> Dict[str, Any]:
        """Build a timeout result dict."""
        return cls(
            score=0.0,
            reason=f"Metric evaluation timed out after {timeout_seconds}s",
            is_successful=False,
            backend=backend,
            name=name,
            class_name=class_name,
            description=description,
            threshold=threshold,
            error_message="Timeout",
            error_type="TimeoutError",
        ).to_dict()
