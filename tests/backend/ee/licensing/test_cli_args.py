"""Tests for the licensing CLI's argument parsers.

These guard a failure mode that is invisible at issuance time: a bad
``--status`` that mints a token which verifies, matches its org and has not
expired, but is treated as unlicensed. The issuance job reports success and the
customer is shown "(inactive)" on a licence they just paid for.
"""

from __future__ import annotations

import argparse

import pytest

from rhesis.backend.ee.licensing.cli import _parse_edition, _parse_status
from rhesis.backend.ee.licensing.entitlements import (
    ACTIVE_STATUSES,
    LicenseEdition,
    LicenseStatus,
)

pytestmark = pytest.mark.skipif(
    not pytest.importorskip("rhesis.backend.ee", reason="EE package not installed"),
    reason="EE package not installed",
)


class TestParseStatus:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("active", LicenseStatus.ACTIVE),
            ("past_due", LicenseStatus.PAST_DUE),
            ("canceled", LicenseStatus.CANCELED),
        ],
    )
    def test_accepts_every_mintable_status(self, value, expected):
        assert _parse_status(value) is expected

    @pytest.mark.parametrize(
        "value",
        ["Active", "ACTIVE", "aCtIvE", " active", "active ", "activ", "enabled", ""],
        ids=[
            "title-case",
            "upper-case",
            "mixed-case",
            "leading-space",
            "trailing-space",
            "typo",
            "wrong-word",
            "empty",
        ],
    )
    def test_rejects_anything_that_is_not_an_exact_status(self, value):
        """The bug this file exists for.

        ``LicenseStatus._missing_`` coerces an unrecognized value to ``UNKNOWN``
        instead of raising, so the parser's original ``except ValueError`` never
        fired. Every value here used to mint ``status: unknown`` -- which is
        absent from ``ACTIVE_STATUSES``, so the org got its edition reported with
        ``licensed: False`` and was held to community limits, with nothing in the
        issuance output indicating a problem.

        The empty string is not hypothetical: it is what a blank CI input
        expands to when passed through as ``--status "${INPUT}"``.
        """
        with pytest.raises(argparse.ArgumentTypeError) as excinfo:
            _parse_status(value)
        # The message must list the real options, since the operator is being
        # told their input was wrong at the moment they can still fix it.
        assert "active" in str(excinfo.value)

    def test_rejects_the_unknown_sentinel_explicitly(self):
        """``unknown`` is a decode-time sentinel for a status we do not
        recognize, never something to mint deliberately."""
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_status(LicenseStatus.UNKNOWN.value)

    def test_no_accepted_status_is_silently_inactive(self):
        """Whatever the parser accepts must be a status the operator could have
        intended. ``canceled`` is inactive but explicitly asked for; the failure
        mode was accepting something that *looked* active and was not."""
        for value in ("active", "past_due"):
            assert _parse_status(value) in ACTIVE_STATUSES
        assert _parse_status("canceled") not in ACTIVE_STATUSES


class TestParseEdition:
    def test_accepts_a_sellable_edition(self):
        assert _parse_edition("enterprise") is LicenseEdition.ENTERPRISE

    @pytest.mark.parametrize("value", ["Enterprise", "ENTERPRISE", "enterprize", "", "unknown"])
    def test_rejects_anything_not_in_the_catalog(self, value):
        """Already correct -- it validates catalog membership after coercion
        rather than trusting ``LicenseEdition(...)`` to raise. Pinned so it does
        not regress into the shape ``_parse_status`` was in."""
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_edition(value)
