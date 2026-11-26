"""Deadline: wall-clock limits a job enforces on itself."""

import pytest

from rhesis.backend.app.utils.deadline import Deadline, JobTimeLimitExceeded


@pytest.mark.unit
class TestDeadline:
    def test_check_passes_before_and_raises_after(self):
        Deadline(60, "Job").check()

        with pytest.raises(JobTimeLimitExceeded, match="Job stopped after 0s"):
            Deadline(0, "Job").check()

    def test_guard_stops_code_that_catches_exception(self):
        # The SDK synthesizers catch Exception around their progress reports.
        def generate(on_progress):
            for i in range(3):
                try:
                    on_progress(i, 3)
                except Exception:
                    pass
            return "finished"

        deadline = Deadline(0, "Generation")
        with pytest.raises(JobTimeLimitExceeded, match="Generation stopped"):
            with deadline.enforced():
                generate(deadline.guard())

    def test_guard_reports_progress_until_the_deadline(self):
        seen = []
        deadline = Deadline(60, "Generation")

        with deadline.enforced():
            deadline.guard(lambda current, total: seen.append(current))(1, 2)

        assert seen == [1]
