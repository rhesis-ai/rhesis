"""Configuration classes for native judge metrics.

This module provides base configuration classes and validation functions to reduce duplication
between single-turn and conversational metrics configurations.
"""

from dataclasses import dataclass
from typing import List, Optional, Union

from rhesis.sdk.metrics.base import MetricConfig
from rhesis.sdk.metrics.constants import ThresholdOperator


@dataclass
class BaseJudgeConfig(MetricConfig):
    """
    Base configuration for all judge metrics.

    Includes fields common to both single-turn and conversational judges:
    - evaluation_prompt: Main evaluation criteria
    - evaluation_steps: Step-by-step evaluation process
    - reasoning: Reasoning guidelines
    - evaluation_examples: Examples to guide evaluation
    """

    evaluation_prompt: Optional[str] = None
    evaluation_steps: Optional[str] = None
    reasoning: Optional[str] = None
    evaluation_examples: Optional[str] = None

    def __post_init__(self):
        return super().__post_init__()


def validate_score_range(min_score: Optional[float], max_score: Optional[float]) -> None:
    """
    Validate that min_score and max_score are provided together and are valid.

    Args:
        min_score: Minimum score value
        max_score: Maximum score value

    Raises:
        ValueError: If only one of min_score or max_score is provided
        ValueError: If min_score and max_score are the same
        ValueError: If min_score is greater than max_score
    """
    if min_score is not None and max_score is None:
        raise ValueError("Only min_score was set, please set max_score")

    if min_score is None and max_score is not None:
        raise ValueError("Only max_score was set, please set min_score")

    if min_score is not None and max_score is not None and min_score == max_score:
        raise ValueError("min_score and max_score cannot be the same")

    if min_score is not None and max_score is not None and min_score > max_score:
        raise ValueError("min_score cannot be greater than max_score")


def set_score_parameters(
    config: Union["NumericJudgeConfig", "ConversationalNumericConfig"],
    min_score: Optional[float],
    max_score: Optional[float],
    threshold: Optional[float],
) -> None:
    """
    Set up score parameters with validation and defaults.

    This function sets the min_score, max_score, and threshold values with appropriate
    defaults and validation.

    Args:
        config: The config object to update
        min_score: Minimum possible score (defaults to 0.0)
        max_score: Maximum possible score (defaults to 1.0)
        threshold: Success threshold (defaults to midpoint)

    Raises:
        ValueError: If threshold is outside the [min_score, max_score] range
    """
    # For numeric scores, we need min_score, max_score, and threshold
    config.min_score = min_score if min_score is not None else 0
    config.max_score = max_score if max_score is not None else 1

    if threshold is None:
        config.threshold = config.min_score + (config.max_score - config.min_score) / 2
    else:
        config.threshold = threshold

    if not (config.min_score <= config.threshold <= config.max_score):
        raise ValueError(f"Threshold must be between {config.min_score} and {config.max_score}")


@dataclass
class NumericJudgeConfig(BaseJudgeConfig):
    """
    Configuration for single-turn numeric judge metrics.

    Combines base judge configuration with numeric scoring fields.
    """

    min_score: Optional[float] = None
    max_score: Optional[float] = None
    threshold: Optional[float] = None
    threshold_operator: Union[ThresholdOperator, str] = ThresholdOperator.GREATER_THAN_OR_EQUAL

    def __post_init__(self):
        # Convert string to enum if needed
        if isinstance(self.threshold_operator, str):
            self.threshold_operator = ThresholdOperator(self.threshold_operator)
        validate_score_range(self.min_score, self.max_score)
        set_score_parameters(self, self.min_score, self.max_score, self.threshold)
        super().__post_init__()


@dataclass
class ConversationalNumericConfig(BaseJudgeConfig):
    """
    Configuration for conversational numeric judge metrics.

    Combines base judge configuration with numeric scoring fields.
    By default, conversational judges use numeric scoring with thresholds.
    """

    min_score: Optional[float] = None
    max_score: Optional[float] = None
    threshold: Optional[float] = None
    threshold_operator: Union[ThresholdOperator, str] = ThresholdOperator.GREATER_THAN_OR_EQUAL

    def __post_init__(self):
        # Convert string to enum if needed
        if isinstance(self.threshold_operator, str):
            self.threshold_operator = ThresholdOperator(self.threshold_operator)
        validate_score_range(self.min_score, self.max_score)
        set_score_parameters(self, self.min_score, self.max_score, self.threshold)
        return super().__post_init__()


@dataclass
class CategoricalJudgeConfig(BaseJudgeConfig):
    """
    Configuration for categorical judge metrics.

    Combines base judge configuration with categorical scoring fields.
    """

    categories: Optional[List[str]] = None
    passing_categories: Optional[Union[str, List[str]]] = None

    def __post_init__(self):
        self._validate_categories()
        self._validate_passing_categories()
        self._normalize_passing_categories()
        self._validate_passing_categories_subset()
        return super().__post_init__()

    def _validate_categories(self) -> None:
        """
        Validate that categories is a valid list with at least 2 scores.

        Raises:
            ValueError: If categories is not a list or has fewer than 2 items
        """
        if not isinstance(self.categories, list) or len(self.categories) < 2:
            raise ValueError(
                f"categories must be a list with at least 2 scores, got: {self.categories}"
            )

    def _validate_passing_categories(self) -> None:
        """
        Validate that passing_categories is a string or list.

        Raises:
            ValueError: If passing_categories is not a string or list
        """
        if not isinstance(self.passing_categories, (str, list)):
            raise ValueError(
                f"passing_categories must be a string or list, got: {type(self.passing_categories)}"
            )

    def _normalize_passing_categories(self) -> None:
        """
        Convert string passing_categories to list for consistent handling.

        This method ensures that passing_categories is always a list, converting
        single string values to single-item lists.
        """
        if isinstance(self.passing_categories, str):
            self.passing_categories = [self.passing_categories]

    def _validate_passing_categories_subset(self) -> None:
        """
        Validate that passing_categories is a subset of categories.

        Raises:
            ValueError: If passing_categories contains values not in categories
            ValueError: If passing_categories has more items than categories
        """
        if len(self.passing_categories) > len(self.categories):
            raise ValueError(
                f"The number of passing_categories ({len(self.passing_categories)}) must be "
                f"less than or equal to the number of categories ({len(self.categories)})"
            )

        if not set(self.passing_categories).issubset(set(self.categories)):
            missing_scores = set(self.passing_categories) - set(self.categories)
            raise ValueError(
                f"Each value in passing_categories must be present in categories. "
                f"Missing scores: {missing_scores}\n"
                f"Given passing_categories: {self.passing_categories}\n"
                f"Given categories: {self.categories}"
            )
