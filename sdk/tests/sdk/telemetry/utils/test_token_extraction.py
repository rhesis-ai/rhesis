"""Tests for provider-agnostic token extraction utilities."""

from rhesis.sdk.telemetry.utils.token_extraction import extract_token_usage, get_first_value


class TestGetFirstValue:
    """Tests for get_first_value helper function."""

    def test_finds_first_key(self):
        """Should return value from first matching key."""
        data = {"key2": 42, "key3": 100}
        result = get_first_value(data, ["key1", "key2", "key3"])
        assert result == 42

    def test_returns_default_when_no_keys_found(self):
        """Should return default when no keys match."""
        data = {"other": 42}
        result = get_first_value(data, ["key1", "key2"], default=0)
        assert result == 0

    def test_skips_none_values(self):
        """Should skip None values and continue searching."""
        data = {"key1": None, "key2": 42}
        result = get_first_value(data, ["key1", "key2"])
        assert result == 42

    def test_skips_zero_values(self):
        """Should skip zero values and continue searching."""
        data = {"key1": 0, "key2": 42}
        result = get_first_value(data, ["key1", "key2"])
        assert result == 42

    def test_converts_to_int(self):
        """Should convert string numbers to int."""
        data = {"key1": "42"}
        result = get_first_value(data, ["key1"])
        assert result == 42
        assert isinstance(result, int)


class TestExtractTokenUsage:
    """Tests for extract_token_usage function."""

    def test_openai_format(self):
        """Should extract tokens from OpenAI format."""
        usage = {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        }
        input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
        assert input_tokens == 10
        assert output_tokens == 20
        assert total_tokens == 30

    def test_anthropic_format(self):
        """Should extract tokens from Anthropic format."""
        usage = {
            "input_tokens": 15,
            "output_tokens": 25,
            "total_tokens": 40,
        }
        input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
        assert input_tokens == 15
        assert output_tokens == 25
        assert total_tokens == 40

    def test_gemini_format(self):
        """Should extract tokens from Gemini format."""
        usage = {
            "prompt_token_count": 12,
            "candidates_token_count": 18,
        }
        input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
        assert input_tokens == 12
        assert output_tokens == 18
        assert total_tokens == 30  # Calculated

    def test_mixed_format(self):
        """Should handle mixed key names (provider-agnostic)."""
        usage = {
            "input_tokens": 8,
            "generated_tokens": 16,
        }
        input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
        assert input_tokens == 8
        assert output_tokens == 16
        assert total_tokens == 24  # Calculated

    def test_calculates_total_when_missing(self):
        """Should calculate total when not provided."""
        usage = {
            "prompt_tokens": 5,
            "completion_tokens": 10,
        }
        input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
        assert total_tokens == 15

    def test_empty_dict(self):
        """Should return zeros for empty dict."""
        input_tokens, output_tokens, total_tokens = extract_token_usage({})
        assert input_tokens == 0
        assert output_tokens == 0
        assert total_tokens == 0

    def test_none_dict(self):
        """Should return zeros for None."""
        input_tokens, output_tokens, total_tokens = extract_token_usage(None)
        assert input_tokens == 0
        assert output_tokens == 0
        assert total_tokens == 0

    def test_partial_data(self):
        """Should handle partial token data gracefully."""
        usage = {"prompt_tokens": 10}
        input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
        assert input_tokens == 10
        assert output_tokens == 0
        assert total_tokens == 10  # Calculated from input only

    def test_prefers_explicit_total(self):
        """Should use explicit total over calculated total."""
        usage = {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 35,  # Explicit total (might include overhead)
        }
        input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
        assert total_tokens == 35  # Should use explicit value

    def test_key_priority_order(self):
        """Should respect key priority order (first in search list wins)."""
        usage = {
            "input_tokens": 10,
            "prompt_tokens": 999,  # Should be ignored (input_tokens checked first)
            "output_tokens": 20,
            "completion_tokens": 999,  # Should be ignored (output_tokens checked first)
        }
        input_tokens, output_tokens, total_tokens = extract_token_usage(usage)
        assert input_tokens == 10  # input_tokens is first in search order
        assert output_tokens == 20  # output_tokens is first in search order
