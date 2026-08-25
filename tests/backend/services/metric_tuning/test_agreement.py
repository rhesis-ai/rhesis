"""Unit tests for the agreement fold — accepted over accepted plus rejected.

The denominator is the whole design, so these drive it directly rather than
through a run: every tempting shortcut inflates it, and each one is a case here.
A pure function over outcomes, so no database and no metric.

Run with: python -m pytest tests/backend/services/metric_tuning/test_agreement.py -v
"""

import pytest

from rhesis.backend.app.schemas.metric_tuning import TuningCaseOutcome
from rhesis.backend.app.services.metric_tuning.agreement import agreement_over

ACCEPTED = TuningCaseOutcome.ACCEPTED
REJECTED = TuningCaseOutcome.REJECTED
ERRORED = TuningCaseOutcome.ERRORED
UNREVIEWED = TuningCaseOutcome.UNREVIEWED


@pytest.mark.unit
class TestTheRatio:
    def test_agreement_is_accepted_over_accepted_plus_rejected(self):
        agreement = agreement_over([ACCEPTED, ACCEPTED, ACCEPTED, REJECTED])

        assert agreement.ratio == 0.75
        assert agreement.judged == 4

    def test_everything_accepted_is_full_agreement(self):
        assert agreement_over([ACCEPTED, ACCEPTED]).ratio == 1.0

    def test_everything_rejected_is_none_of_it(self):
        assert agreement_over([REJECTED, REJECTED]).ratio == 0.0

    def test_a_repeating_ratio_is_rounded_rather_than_sent_raw(self):
        """0.6667 reads as a share. 0.6666666666666666 reads as a bug."""
        assert agreement_over([ACCEPTED, ACCEPTED, REJECTED]).ratio == 0.6667


@pytest.mark.unit
class TestWhatIsLeftOutOfTheDenominator:
    def test_an_unreviewed_case_is_not_counted_as_accepted(self):
        """The shortcut that makes a set nobody looked at report itself perfect."""
        agreement = agreement_over([ACCEPTED, UNREVIEWED, UNREVIEWED])

        assert agreement.ratio == 1.0
        assert agreement.judged == 1
        assert agreement.unreviewed == 2

    def test_an_errored_case_is_not_counted_as_rejected(self):
        """The shortcut that makes a flaky provider read as a bad metric."""
        agreement = agreement_over([ACCEPTED, ERRORED, ERRORED])

        assert agreement.ratio == 1.0
        assert agreement.judged == 1
        assert agreement.errored == 2

    def test_nothing_judged_has_no_agreement_rather_than_full_agreement(self):
        agreement = agreement_over([UNREVIEWED, UNREVIEWED, ERRORED])

        assert agreement.ratio is None
        assert agreement.judged == 0

    def test_no_cases_at_all_has_no_agreement(self):
        agreement = agreement_over([])

        assert agreement.ratio is None
        assert agreement.judged == 0
        assert agreement.unreviewed == 0
        assert agreement.errored == 0


@pytest.mark.unit
class TestTheCountsBesideIt:
    def test_every_case_lands_in_exactly_one_count(self):
        """The four never collapse into fewer, and none of them double-count."""
        outcomes = [ACCEPTED, ACCEPTED, REJECTED, UNREVIEWED, ERRORED]

        agreement = agreement_over(outcomes)

        assert agreement.accepted == 2
        assert agreement.rejected == 1
        assert agreement.unreviewed == 1
        assert agreement.errored == 1
        assert (
            agreement.accepted + agreement.rejected + agreement.unreviewed + agreement.errored
            == len(outcomes)
        )

    def test_judged_is_the_denominator_and_nothing_else(self):
        agreement = agreement_over([ACCEPTED, REJECTED, UNREVIEWED, ERRORED])

        assert agreement.judged == 2
