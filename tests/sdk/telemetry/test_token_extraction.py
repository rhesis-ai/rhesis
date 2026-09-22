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


class TestRealProviderUsageObjects:
    """The usage types each provider's own client returns.

    Hand-written dicts cannot catch the bug these guard: a dict skips the
    object-flattening path entirely, which is where the counts were being dropped.
    Building the real type costs nothing at test time, needs no API key and makes no
    network call, and it fails the day a provider changes the shape underneath us.
    """

    def test_openai(self):
        from openai.types import CompletionUsage

        usage = CompletionUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        assert extract_token_usage(usage) == (10, 20, 30)

    def test_anthropic(self):
        from anthropic.types import Usage

        usage = Usage(input_tokens=50, output_tokens=20)

        assert extract_token_usage(usage) == (50, 20, 70)

    def test_anthropic_keeps_cache_tokens_alongside_the_plain_ones(self):
        """Anthropic bills cache reads and writes, so they belong in the total.

        This held before the flattening rewrite too, but only because the two cache
        names had been added to the copied list by hand after they went missing once.
        It is pinned against the real type so the next Anthropic release cannot quietly
        rename them.
        """
        from anthropic.types import Usage

        usage = Usage(
            input_tokens=50,
            output_tokens=20,
            cache_creation_input_tokens=1000,
            cache_read_input_tokens=4000,
        )

        assert extract_token_usage(usage) == (50, 20, 5070)

    def test_mistral(self):
        from mistralai.models import UsageInfo

        usage = UsageInfo(prompt_tokens=11, completion_tokens=22, total_tokens=33)

        assert extract_token_usage(usage) == (11, 22, 33)

    def test_cohere_reads_the_billed_figure_not_the_raw_one(self):
        """Cohere nests its counts, and reports two of them.

        Billed is what the invoice charges, and cost is what these numbers feed. Before
        the nesting was handled at all, a Cohere call reported (0, 0, 0).
        """
        from cohere.types import Usage, UsageBilledUnits, UsageTokens

        usage = Usage(
            billed_units=UsageBilledUnits(input_tokens=7, output_tokens=3),
            tokens=UsageTokens(input_tokens=9, output_tokens=4),
        )

        assert extract_token_usage(usage) == (7, 3, 10)

    def test_google(self):
        from google.genai.types import GenerateContentResponseUsageMetadata

        usage = GenerateContentResponseUsageMetadata(
            prompt_token_count=15, candidates_token_count=25, total_token_count=40
        )

        assert extract_token_usage(usage) == (15, 25, 40)


class TestFlatteningKeepsEverything:
    """One recognised name must not hide the rest of the payload.

    This is the shape of the old bug, independent of any one provider: the copy was
    keyed off a hardcoded list, so a payload mixing a listed name with an unlisted one
    lost the second silently.
    """

    def test_a_listed_name_does_not_discard_an_unlisted_one(self):
        class Usage:
            input_tokens = 50
            output_tokens = 20
            cacheReadInputTokens = 4000  # the provider's own spelling

        assert extract_token_usage(Usage()) == (50, 20, 4070)

    def test_camel_case_keys_are_read(self):
        usage = {
            "promptTokenCount": 15,
            "candidatesTokenCount": 25,
            "totalTokenCount": 40,
        }

        assert extract_token_usage(usage) == (15, 25, 40)

    def test_a_top_level_count_beats_a_nested_one(self):
        usage = {"input_tokens": 99, "billed_units": {"input_tokens": 7, "output_tokens": 3}}

        input_tokens, output_tokens, _ = extract_token_usage(usage)

        assert (input_tokens, output_tokens) == (99, 3)

    def test_an_explicit_zero_is_reported_as_zero(self):
        assert extract_token_usage({"prompt_tokens": 7, "completion_tokens": 0}) == (7, 0, 7)

    def test_an_empty_payload_is_zeroes(self):
        assert extract_token_usage({}) == (0, 0, 0)

    def test_an_object_that_cannot_be_flattened_is_zeroes(self):
        assert extract_token_usage(object()) == (0, 0, 0)

    def test_an_attribute_that_raises_is_skipped_not_propagated(self):
        """Telemetry must not take the caller's request down with it.

        Reading an attribute can run arbitrary code, and getattr's default only
        swallows AttributeError, so a lazy property that fails for its own reasons
        used to escape into the request that was only trying to be traced.
        """

        class Usage:
            input_tokens = 50
            output_tokens = 20

            @property
            def total_tokens(self):
                raise RuntimeError("lazy load failed")

        assert extract_token_usage(Usage()) == (50, 20, 70)
