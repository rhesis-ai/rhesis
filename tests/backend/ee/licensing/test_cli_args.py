"""Tests for the licensing CLI's argument parsers.

These guard a failure mode that is invisible at issuance time: a bad
``--status`` that mints a token which verifies, matches its org and has not
expired, but is treated as unlicensed. The issuance job reports success and the
customer is shown "(inactive)" on a licence they just paid for.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import pytest

from rhesis.backend.ee.licensing.cli import (
    _build_parser,
    _parse_edition,
    _parse_expires_at,
    _parse_jti,
    _parse_status,
)
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


class TestPinnedClaimArgs:
    """``--jti``/``--expires-at``: how rhesis-ee's registry pins a grant's id
    and contract-derived expiry before the token is minted."""

    def test_jti_is_normalized(self):
        assert (
            _parse_jti("3F2B8C1E-5D4A-4E6F-9A7B-1C2D3E4F5A6B")
            == "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b"
        )

    @pytest.mark.parametrize(
        "value", ["", "abc", "3f2b8c1e", "00000000-0000-0000-0000-000000000000"]
    )
    def test_a_malformed_jti_is_rejected(self, value):
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_jti(value)

    @pytest.mark.parametrize(
        "value",
        ["2028-01-15T00:00:00Z", "2028-01-15T00:00:00+00:00", "2028-01-15T00:00:00", "2028-01-15"],
    )
    def test_expires_at_forms_all_mean_utc_midnight(self, value):
        assert _parse_expires_at(value) == datetime(2028, 1, 15, tzinfo=timezone.utc)

    @pytest.mark.parametrize(
        "value",
        ["next year", "2020-01-01", "2028-01-15T00:00:00.5Z"],
        ids=["prose", "past", "fraction"],
    )
    def test_a_bad_expiry_is_rejected_before_anything_is_minted(self, value):
        with pytest.raises(argparse.ArgumentTypeError):
            _parse_expires_at(value)

    def test_lowercase_z_is_accepted(self):
        assert _parse_expires_at("2028-01-15t00:00:00z") == datetime(
            2028, 1, 15, tzinfo=timezone.utc
        )

    @pytest.mark.parametrize("command", ["mint", "issue"])
    def test_expires_at_and_ttl_days_are_mutually_exclusive(self, command):
        with pytest.raises(SystemExit):
            _build_parser().parse_args(
                [
                    command,
                    "--org",
                    "x",
                    "--edition",
                    "team",
                    "--ttl-days",
                    "5",
                    "--expires-at",
                    "2028-01-15",
                ]
            )

    @pytest.mark.parametrize("command", ["mint", "issue"])
    def test_both_flags_reach_the_parsed_args(self, command):
        args = _build_parser().parse_args(
            [
                command,
                "--org",
                "x",
                "--edition",
                "team",
                "--expires-at",
                "2028-01-15",
                "--jti",
                "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b",
            ]
        )
        assert args.expires_at == datetime(2028, 1, 15, tzinfo=timezone.utc)
        assert args.jti == "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b"


class TestPinnedClaimsPassThrough:
    """The handlers must hand --jti/--expires-at to the minting code; if one
    stopped, the token would carry a different id or expiry than the registry
    recorded, with nothing failing."""

    JTI = "3f2b8c1e-5d4a-4e6f-9a7b-1c2d3e4f5a6b"
    ARGS = [
        "--org",
        "00000000-0000-0000-0000-000000000011",
        "--edition",
        "team",
        "--expires-at",
        "2028-01-15",
        "--jti",
        JTI,
    ]

    def _run(self, monkeypatch, command, *extra):
        from unittest.mock import patch

        from rhesis.backend.ee.licensing import cli

        monkeypatch.setenv("RHESIS_LICENSE_PRIVATE_KEY", "unused: mint_token is patched")
        args = cli._build_parser().parse_args([command, *self.ARGS, *extra])
        with (
            patch("rhesis.backend.ee.licensing.mint.mint_token", return_value="tok") as mint,
            patch.object(cli, "_print_summary"),
        ):
            args.func(args)
        return mint

    def _assert_pinned(self, mint):
        kwargs = mint.call_args.kwargs
        assert kwargs["jti"] == self.JTI
        assert kwargs["expires_at"] == datetime(2028, 1, 15, tzinfo=timezone.utc)

    def test_mint(self, monkeypatch, capsys):
        self._assert_pinned(self._run(monkeypatch, "mint"))

    def test_issue_dry_run(self, monkeypatch):
        self._assert_pinned(self._run(monkeypatch, "issue", "--dry-run"))
