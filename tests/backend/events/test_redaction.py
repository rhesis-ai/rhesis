"""Key-name based redaction. See redaction.py's docstring for what this
filter does and does not catch -- it inspects key names, never values.
"""

from rhesis.backend.events.redaction import redact_metadata


class TestRedactMetadata:
    def test_drops_exact_match_keys(self):
        assert redact_metadata({"username": "john", "password": "secret"}) == {"username": "john"}

    def test_case_insensitive(self):
        assert redact_metadata({"Password": "x", "PASSWORD": "y", "keep": "z"}) == {"keep": "z"}

    def test_substring_rule_catches_variations_the_exact_match_set_misses(self):
        """'email' is an exact-match key; 'user_email' is not -- the
        substring rule is what catches it, and this is the gap the design
        doc calls out as worth widening when the list moves."""
        assert redact_metadata({"user_email": "a@b.com", "user_agent": "Mozilla"}) == {
            "user_agent": "Mozilla"
        }

    def test_substring_rule_catches_api_secret_and_access_token_variants(self):
        assert redact_metadata({"api_secret_key": "x", "count": 3}) == {"count": 3}

    def test_leaves_ordinary_keys_alone(self):
        data = {"job_type": "generate_and_save_test_set", "total_tests": 40}
        assert redact_metadata(data) == data

    def test_empty_dict(self):
        assert redact_metadata({}) == {}
