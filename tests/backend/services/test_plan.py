"""Unit tests for :func:`~rhesis.backend.app.services.plan.build_plan`.

The label this composes is rendered verbatim by clients, and the two booleans
decide badge styling and whether an upgrade is offered. Both were previously
only covered indirectly through the endpoint's response shape, which asserted
types rather than values.
"""

from __future__ import annotations

import pytest

from rhesis.backend.app.services.plan import build_plan


class TestLabel:
    @pytest.mark.parametrize(
        ("edition", "expected"),
        [
            # Not "Community": the pricing page advertises this tier as Free.
            ("community", "Free"),
            ("team", "Team"),
            ("enterprise", "Enterprise"),
            # Separators become spaces, so a multi-word tier id reads as prose
            # rather than as an identifier.
            ("design_partner", "Design Partner"),
            ("design-partner", "Design Partner"),
        ],
    )
    def test_composes_a_display_label_from_the_edition_id(self, edition, expected):
        plan = build_plan({"edition": edition, "licensed": True, "is_paid": True})
        assert plan["name"] == expected

    def test_an_unrecognised_tier_still_gets_a_label(self):
        """The property that lets a new tier ship without a frontend release:
        nothing here knows the set of tiers."""
        plan = build_plan({"edition": "hyperscale_plus", "licensed": True, "is_paid": True})
        assert plan["name"] == "Hyperscale Plus"

    def test_never_returns_an_empty_label(self):
        """A blank edition must not render as an empty badge. Clients treat an
        empty name as "no plan yet" and show nothing, which would hide the
        plan row entirely rather than showing something is wrong."""
        assert build_plan({"edition": "   "})["name"] == "Unknown"
        assert build_plan({})["name"] == "Free"

    def test_the_free_tier_is_named_as_the_pricing_page_advertises_it(self):
        """``community`` is the internal id; the pricing page sells it as the
        Free plan (see FREE_TIER_LIMITS and tier_config.yaml's header). Since
        ``name`` is rendered verbatim, title-casing the id put "Community" in
        the sidebar and usage page beside limits published as Free.

        The mapping is an exception list over the title-case default, not a
        replacement for it, so the unrecognised-tier property above still holds.
        """
        assert build_plan({"edition": "community"})["name"] == "Free"
        assert build_plan({"edition": "COMMUNITY"})["name"] == "Free"


class TestLapsedQualifier:
    def test_a_lapsed_paid_tier_is_marked_in_the_label(self):
        """Carried in the text, not only in the styling, so the state survives
        a screenshot, a narrow column and a monochrome theme."""
        plan = build_plan({"edition": "enterprise", "licensed": False, "is_paid": True})
        assert plan["name"] == "Enterprise (inactive)"
        assert plan["is_paid"] is True
        assert plan["is_active"] is False

    def test_an_active_paid_tier_carries_no_qualifier(self):
        plan = build_plan({"edition": "enterprise", "licensed": True, "is_paid": True})
        assert plan["name"] == "Enterprise"

    def test_a_free_tier_carries_no_qualifier(self):
        """A free org is not "inactive" -- it has nothing to reactivate. Only a
        tier that was paid for gets the qualifier."""
        plan = build_plan({"edition": "community", "licensed": False, "is_paid": False})
        assert plan["name"] == "Free"
        assert plan["is_paid"] is False
        assert plan["is_active"] is False


class TestFlags:
    def test_separates_a_free_org_from_a_lapsed_paid_one(self):
        """The pair this exists for. Both are held to free-tier ceilings, but
        only one of them bought something, and a single flag cannot say which.
        """
        free = build_plan({"edition": "community", "licensed": False, "is_paid": False})
        lapsed = build_plan({"edition": "team", "licensed": False, "is_paid": True})

        assert (free["is_paid"], free["is_active"]) == (False, False)
        assert (lapsed["is_paid"], lapsed["is_active"]) == (True, False)

    def test_missing_flags_default_to_the_free_posture(self):
        """Fail-closed: an unknown posture must never present as paid."""
        plan = build_plan({"edition": "team"})
        assert plan["is_paid"] is False
        assert plan["is_active"] is False

    @pytest.mark.parametrize("truthy", [1, "yes", ["x"]])
    def test_coerces_non_bool_values_rather_than_leaking_them(self, truthy):
        """The wire contract is booleans. A provider returning something
        truthy-but-not-bool must not put that value on the response, where a
        client comparing `is_paid === true` would read it as false."""
        plan = build_plan({"edition": "team", "licensed": truthy, "is_paid": truthy})
        assert plan["is_paid"] is True
        assert plan["is_active"] is True
