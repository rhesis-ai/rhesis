"""
Tests for ScoreEvaluator - validates score evaluation logic for categorical and numeric metrics.
"""

import pytest

from rhesis.backend.metrics.score_evaluator import ScoreEvaluator
from rhesis.backend.metrics.constants import ScoreType, ThresholdOperator


class TestScoreEvaluator:
    """Test ScoreEvaluator functionality."""
    
    @pytest.fixture
    def evaluator(self):
        """Create a ScoreEvaluator instance."""
        return ScoreEvaluator()
    
    # ============================================================================
    # CATEGORICAL METRICS WITH PASSING_CATEGORIES
    # ============================================================================
    
    def test_categorical_with_passing_categories_success(self, evaluator):
        """Test categorical metric with score in passing_categories."""
        result = evaluator.evaluate_score(
            score="True",
            threshold=None,
            threshold_operator="=",
            categories=["True", "False"],
            passing_categories=["True"],
        )
        assert result is True
    
    def test_categorical_with_passing_categories_failure(self, evaluator):
        """Test categorical metric with score not in passing_categories."""
        result = evaluator.evaluate_score(
            score="False",
            threshold=None,
            threshold_operator="=",
            categories=["True", "False"],
            passing_categories=["True"],
        )
        assert result is False
    
    def test_categorical_case_insensitive(self, evaluator):
        """Test categorical evaluation is case-insensitive."""
        result = evaluator.evaluate_score(
            score="true",  # lowercase
            threshold=None,
            threshold_operator="=",
            categories=["True", "False"],  # mixed case
            passing_categories=["True"],
        )
        assert result is True
    
    def test_categorical_with_whitespace(self, evaluator):
        """Test categorical evaluation handles whitespace."""
        result = evaluator.evaluate_score(
            score="  True  ",  # with whitespace
            threshold=None,
            threshold_operator="=",
            categories=["True", "False"],
            passing_categories=["True"],
        )
        assert result is True
    
    def test_categorical_multiple_passing_categories(self, evaluator):
        """Test categorical metric with multiple passing categories."""
        result_pass = evaluator.evaluate_score(
            score="pass",
            threshold=None,
            threshold_operator="=",
            categories=["pass", "fail", "skip"],
            passing_categories=["pass", "skip"],
        )
        assert result_pass is True
        
        result_skip = evaluator.evaluate_score(
            score="skip",
            threshold=None,
            threshold_operator="=",
            categories=["pass", "fail", "skip"],
            passing_categories=["pass", "skip"],
        )
        assert result_skip is True
        
        result_fail = evaluator.evaluate_score(
            score="fail",
            threshold=None,
            threshold_operator="=",
            categories=["pass", "fail", "skip"],
            passing_categories=["pass", "skip"],
        )
        assert result_fail is False
    
    def test_categorical_not_equal_operator(self, evaluator):
        """Test categorical metric with != operator."""
        result = evaluator.evaluate_score(
            score="False",
            threshold=None,
            threshold_operator="!=",
            categories=["True", "False"],
            passing_categories=["True"],
        )
        # With !=, we expect True when score is NOT in passing_categories
        assert result is True
    
    def test_categorical_missing_categories_and_reference(self, evaluator):
        """Test that categorical metric requires either passing_categories or reference_score."""
        with pytest.raises(ValueError) as exc_info:
            evaluator.evaluate_score(
                score="True",
                threshold=None,
                threshold_operator="=",
                # No passing_categories, no reference_score
            )
        assert "Either passing_categories or reference_score is required" in str(exc_info.value)
    
    # ============================================================================
    # CATEGORICAL METRICS WITH REFERENCE_SCORE (LEGACY)
    # ============================================================================
    
    def test_categorical_with_reference_score_legacy(self, evaluator):
        """Test categorical metric with legacy reference_score."""
        result = evaluator.evaluate_score(
            score="pass",
            threshold=None,
            threshold_operator="=",
            reference_score="pass",
        )
        assert result is True
    
    def test_categorical_with_reference_score_failure(self, evaluator):
        """Test categorical metric with reference_score not matching."""
        result = evaluator.evaluate_score(
            score="fail",
            threshold=None,
            threshold_operator="=",
            reference_score="pass",
        )
        assert result is False
    
    # ============================================================================
    # NUMERIC METRICS
    # ============================================================================
    
    def test_numeric_greater_than_or_equal(self, evaluator):
        """Test numeric metric with >= operator."""
        result = evaluator.evaluate_score(
            score=0.8,
            threshold=0.7,
            threshold_operator=">=",
        )
        assert result is True
    
    def test_numeric_less_than(self, evaluator):
        """Test numeric metric with < operator."""
        result = evaluator.evaluate_score(
            score=0.5,
            threshold=0.7,
            threshold_operator="<",
        )
        assert result is True
    
    def test_numeric_equal(self, evaluator):
        """Test numeric metric with = operator."""
        result = evaluator.evaluate_score(
            score=0.7,
            threshold=0.7,
            threshold_operator="=",
        )
        assert result is True
    
    def test_numeric_missing_threshold(self, evaluator):
        """Test that numeric metrics require a threshold."""
        with pytest.raises(ValueError) as exc_info:
            evaluator.evaluate_score(
                score=0.8,
                threshold=None,
                threshold_operator=">=",
            )
        assert "Threshold is required for numeric score type" in str(exc_info.value)
    
    # ============================================================================
    # SCORE TYPE DETERMINATION
    # ============================================================================
    
    def test_determine_score_type_string(self, evaluator):
        """Test that string scores are determined as categorical."""
        score_type = evaluator._determine_score_type("True", None)
        assert score_type == ScoreType.CATEGORICAL
    
    def test_determine_score_type_numeric(self, evaluator):
        """Test that numeric scores are determined as numeric."""
        score_type = evaluator._determine_score_type(0.8, None)
        assert score_type == ScoreType.NUMERIC
    
    def test_determine_score_type_int(self, evaluator):
        """Test that integer scores are determined as numeric."""
        score_type = evaluator._determine_score_type(5, None)
        assert score_type == ScoreType.NUMERIC
    
    # ============================================================================
    # OPERATOR SANITIZATION
    # ============================================================================
    
    def test_sanitize_operator_valid_string(self, evaluator):
        """Test sanitizing valid string operator."""
        result = evaluator._sanitize_threshold_operator(">=")
        assert result == ThresholdOperator.GREATER_THAN_OR_EQUAL
    
    def test_sanitize_operator_with_whitespace(self, evaluator):
        """Test sanitizing operator with whitespace."""
        result = evaluator._sanitize_threshold_operator("  >=  ")
        assert result == ThresholdOperator.GREATER_THAN_OR_EQUAL
    
    def test_sanitize_operator_enum(self, evaluator):
        """Test sanitizing already-enum operator."""
        result = evaluator._sanitize_threshold_operator(ThresholdOperator.GREATER_THAN_OR_EQUAL)
        assert result == ThresholdOperator.GREATER_THAN_OR_EQUAL
    
    def test_sanitize_operator_invalid(self, evaluator):
        """Test sanitizing invalid operator returns None."""
        result = evaluator._sanitize_threshold_operator("invalid")
        assert result is None

