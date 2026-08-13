"""Unit tests for rendering a metric's own score as a verdict string.

A narrow seam, tested on its own for the same reason the verdict validation is:
the rules differ per score type, and driving each one through a whole run would
be slow and would bury what is actually being asserted.

Run with: python -m pytest tests/backend/services/metric_tuning/test_invoke.py -v
"""

from types import SimpleNamespace

import pytest

from rhesis.backend.app.services.metric_tuning.invoke import verdict_from_score


def _metric(score_type: str) -> SimpleNamespace:
    """A stand-in for the Metric row — only score_type is read."""
    return SimpleNamespace(score_type=score_type)


class TestBinaryVerdicts:
    """A binary metric returns a number the SDK treats as a flag."""

    @pytest.mark.parametrize("score", [1.0, 1, True, 0.7])
    def test_a_truthy_score_is_pass(self, score):
        assert verdict_from_score(_metric("binary"), score) == "pass"

    @pytest.mark.parametrize("score", [0.0, 0, False])
    def test_a_falsy_score_is_fail(self, score):
        assert verdict_from_score(_metric("binary"), score) == "fail"

    @pytest.mark.parametrize("score", ["pass", "PASS", " Fail "])
    def test_a_metric_that_already_answers_in_words_is_taken_at_its_word(self, score):
        assert verdict_from_score(_metric("binary"), score) == score.strip().lower()

    def test_rendered_as_pass_not_as_one_point_zero(self):
        """`1.0` beside an expected `pass` reads as a disagreement to a human."""
        assert verdict_from_score(_metric("binary"), 1.0) == "pass"


class TestNumericVerdicts:
    def test_a_number_is_its_own_verdict(self):
        assert verdict_from_score(_metric("numeric"), 0.79) == "0.79"

    def test_an_integer_score_normalizes_to_a_float(self):
        assert verdict_from_score(_metric("numeric"), 1) == "1.0"

    def test_a_number_that_arrived_as_a_string_still_normalizes(self):
        assert verdict_from_score(_metric("numeric"), "0.5") == "0.5"

    def test_an_unparseable_score_is_kept_verbatim(self):
        """Better a verdict a human can see is wrong than one silently dropped."""
        assert verdict_from_score(_metric("numeric"), "not a number") == "not a number"


class TestCategoricalVerdicts:
    def test_the_category_is_the_verdict(self):
        assert verdict_from_score(_metric("categorical"), "toxic") == "toxic"


class TestNoScore:
    def test_no_score_is_no_verdict(self):
        """A failed call has no verdict — and must not be given a default one."""
        assert verdict_from_score(_metric("binary"), None) is None
