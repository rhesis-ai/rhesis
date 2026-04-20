"""Tests for Organization slug validation."""

import pytest

from rhesis.backend.app.schemas.organization import OrganizationBase


def _make_org(**kwargs):
    defaults = {"name": "Test Org"}
    defaults.update(kwargs)
    return OrganizationBase(**defaults)


class TestSlugValidation:
    """Test the slug field validator on OrganizationBase."""

    def test_none_accepted(self):
        org = _make_org(slug=None)
        assert org.slug is None

    def test_empty_string_normalised_to_none(self):
        org = _make_org(slug="")
        assert org.slug is None

    def test_whitespace_only_normalised_to_none(self):
        org = _make_org(slug="   ")
        assert org.slug is None

    def test_valid_lowercase_slug(self):
        org = _make_org(slug="acme-corp")
        assert org.slug == "acme-corp"

    def test_valid_numeric_slug(self):
        org = _make_org(slug="123")
        assert org.slug == "123"

    def test_valid_mixed_slug(self):
        org = _make_org(slug="acme-corp-42")
        assert org.slug == "acme-corp-42"

    def test_uppercase_normalised(self):
        org = _make_org(slug="Acme-Corp")
        assert org.slug == "acme-corp"

    def test_leading_trailing_whitespace_stripped(self):
        org = _make_org(slug="  acme-corp  ")
        assert org.slug == "acme-corp"

    def test_minimum_length_3(self):
        org = _make_org(slug="abc")
        assert org.slug == "abc"

    def test_too_short_rejected(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            _make_org(slug="ab")

    def test_single_char_rejected(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            _make_org(slug="a")

    def test_maximum_length_50(self):
        slug = "a" * 50
        org = _make_org(slug=slug)
        assert org.slug == slug

    def test_too_long_rejected(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            _make_org(slug="a" * 51)

    def test_starts_with_hyphen_rejected(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            _make_org(slug="-acme")

    def test_ends_with_hyphen_rejected(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            _make_org(slug="acme-")

    def test_consecutive_hyphens_rejected(self):
        with pytest.raises(ValueError, match="consecutive hyphens"):
            _make_org(slug="acme--corp")

    def test_special_chars_rejected(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            _make_org(slug="acme_corp")

    def test_spaces_in_slug_rejected(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            _make_org(slug="acme corp")

    def test_dots_rejected(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            _make_org(slug="acme.corp")

    def test_at_sign_rejected(self):
        with pytest.raises(ValueError, match="3-50 characters"):
            _make_org(slug="user@acme")
