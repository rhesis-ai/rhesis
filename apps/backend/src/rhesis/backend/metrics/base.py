from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypeVar, Protocol

MetricType = Literal["rag", "generation", "classification"]


@dataclass
class MetricConfig:
    """Standard configuration for a metric instance."""
    
    class_name: str
    """The class name of the metric to instantiate (e.g., 'DeepEvalContextualRecall')"""
    
    backend: str
    """The backend/framework to use for this metric (e.g., 'deepeval')"""
    
    threshold: float = 0.5
    """Threshold for metric success (typically between 0-1)"""
    
    name: Optional[str] = None
    """Human-readable name of the metric"""

    description: Optional[str] = None
    """Human-readable description of what the metric measures"""
    
    parameters: Dict[str, Any] = field(default_factory=dict)
    """Additional parameters specific to this metric implementation"""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the config to a dictionary."""
        result = {
            "class_name": self.class_name,
            "backend": self.backend,
            "threshold": self.threshold,
        }
        
        if self.description:
            result["description"] = self.description
            
        # Add any custom parameters
        result.update(self.parameters)
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricConfig":
        """Create a MetricConfig from a dictionary."""
        # Extract required fields
        class_name = data["class_name"]
        backend = data["backend"]
        
        # Extract optional fields with defaults
        threshold = data.get("threshold", 0.5)
        description = data.get("description")
        name = data.get("name")
        # Extract all other keys as custom parameters
        reserved_keys = {"class_name", "backend", "threshold", "description"}
        parameters = {k: v for k, v in data.items() if k not in reserved_keys}
        
        return cls(
            class_name=class_name,
            backend=backend,
            threshold=threshold,
            description=description,
            name=name,
            parameters=parameters
        )


class MetricResult:
    """Result of a metric evaluation."""

    def __init__(self, score: float, details: Dict[str, Any] = None):
        self.score = score
        self.details = details or {}


class BaseMetric(ABC):
    """Base class for all evaluation metrics."""

    def __init__(self, name: str, metric_type: MetricType = "rag"):
        self._name = name
        self._metric_type = metric_type

    @property
    def name(self) -> str:
        return self._name

    @property
    def metric_type(self) -> MetricType:
        return self._metric_type

    @property
    @abstractmethod
    def requires_ground_truth(self) -> bool:
        """Whether this metric requires a ground truth reference."""
        pass

    @abstractmethod
    def evaluate(
        self, input: str, output: str, expected_output: Optional[str], context: List[str]
    ) -> MetricResult:
        """
        Evaluate the metric on the given input, output, and context.

        Args:
            input: The input query/question
            output: The system output/response
            expected_output: The expected or reference output (ground truth)
            context: List of context chunks used for the response

        Returns:
            MetricResult: The evaluation result
        """
        pass


class BaseMetricFactory(ABC):
    """Base factory interface for creating metric instances."""

    @abstractmethod
    def create(self, class_name: str, **kwargs) -> BaseMetric:
        """Create a metric instance of the specified type."""
        pass

    @abstractmethod
    def list_supported_metrics(self) -> List[str]:
        """List all supported metric types for this factory."""
        pass
