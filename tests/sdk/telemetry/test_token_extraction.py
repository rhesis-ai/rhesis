"""Tests for provider-agnostic token usage extraction."""

from rhesis.telemetry.token_extraction import extract_token_usage


class TestExtractTokenUsage:
    def test_openai_format(self):
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        assert extract_token_usage(usage) == (10, 20, 30)

    def test_anthropic_format_with_cache_tokens(self):
        usage = {
            "input_tokens": 50,
            "output_tokens": 20,
            "cache_creation_input_tokens": 1000,
            "cache_read_input_tokens": 4000,
        }
        input_tk, output_tk, total_tk = extract_token_usage(usage)
        assert input_tk == 50
        assert output_tk == 20
        assert total_tk == 50 + 20 + 1000 + 4000

    def test_anthropic_format_without_cache_tokens(self):
        usage = {"input_tokens": 50, "output_tokens": 20}
        assert extract_token_usage(usage) == (50, 20, 70)

    def test_anthropic_usage_object_keeps_cache_tokens(self):
        """A native Usage object goes through attribute extraction; cache keys must survive it."""

        class Usage:
            input_tokens = 50
            output_tokens = 20
            total_tokens = None
            cache_creation_input_tokens = 1000
            cache_read_input_tokens = 4000

        # Pre-fix, common_attrs dropped the cache keys while input/output made
        # usage_dict truthy, so the object never reached model_dump().
        assert extract_token_usage(Usage()) == (50, 20, 5070)

    def test_explicit_total_is_honored_with_cache_tokens(self):
        """An explicit provider total is used as-is: cache tokens are already inside it."""
        usage = {
            "input_tokens": 50,
            "output_tokens": 20,
            "total_tokens": 70,
            "cache_creation_input_tokens": 1000,
            "cache_read_input_tokens": 4000,
        }
        # Recomputing here would double-count cache tokens (5150 != 70).
        assert extract_token_usage(usage) == (50, 20, 70)

    def test_gemini_format(self):
        usage = {"prompt_token_count": 15, "candidates_token_count": 25}
        assert extract_token_usage(usage) == (15, 25, 40)

    def test_none_returns_zeroes(self):
        assert extract_token_usage(None) == (0, 0, 0)

    def test_cache_only_tokens(self):
        usage = {"cache_creation_input_tokens": 1000, "cache_read_input_tokens": 4000}
        assert extract_token_usage(usage) == (0, 0, 5000)
