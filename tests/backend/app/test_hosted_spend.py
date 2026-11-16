"""Daily hosted-model spend caps (app/quota/hosted_spend.py, app/quota/hosted_pricing.py).

Uses the test Redis container (DB 12), flushed per test. The monitor thread is
never started; tests call ``tick()`` themselves.

Run with:
    cd apps/backend
    uv run pytest ../../tests/backend/app/test_hosted_spend.py -v
"""

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import litellm
import pytest

from rhesis.backend.app.error_handlers import internal_error
from rhesis.backend.app.quota import hosted_pricing
from rhesis.backend.app.quota import hosted_spend as module
from rhesis.backend.app.quota.enforcement import stream_error_message
from rhesis.backend.app.quota.hosted_spend import (
    CAP_OVERRIDE_KEY,
    CAP_REACHED_MARKER,
    CAP_REACHED_MESSAGE,
    MICRO_USD,
    ORG_CAP_OVERRIDE_KEY,
    ORG_CAP_REACHED_MARKER,
    ORG_CAP_REACHED_MESSAGE,
    PRICES_KEY,
    THRESHOLD_MARKER,
    HostedModelCapReached,
    HostedModelOrgCapReached,
    HostedRequestTooLarge,
    HostedSpend,
    day_key,
    seconds_until_reset,
)
from rhesis.backend.app.utils import usage_tracking
from rhesis.backend.app.utils.database_exceptions import handle_database_exceptions
from rhesis.backend.jobs.base import BaseJob
from rhesis.backend.jobs.execution.batch.runner import _failure_result, _is_retriable_failure
from rhesis.sdk.models.base import ModelCallRefused
from rhesis.sdk.models.providers.litellm import LiteLLM
from rhesis.sdk.models.providers.native import PlatformRefusedCall

VERTEX = "vertex_ai/gemini-3.1-flash-lite"
ORG = "org-a"
OTHER_ORG = "org-b"
ONE_M_OUTPUT_USD = 1.50


@pytest.fixture
def limits(monkeypatch):
    """Set the env limits; ``platform=None`` turns the caps off."""

    def _set(platform=10.0, org=None, max_input=200_000):
        monkeypatch.setattr(
            module,
            "get_application_settings",
            lambda: SimpleNamespace(
                hosted_model_daily_budget_usd=platform,
                hosted_model_org_daily_budget_usd=org,
                hosted_model_max_input_tokens=max_input,
            ),
        )

    _set()
    monkeypatch.setattr(
        hosted_pricing,
        "get_model_settings",
        lambda: SimpleNamespace(
            generation_model=VERTEX, evaluation_model=VERTEX, execution_model=VERTEX
        ),
    )
    return _set


@pytest.fixture
def spend(limits):
    instance = HostedSpend()
    with patch.object(instance, "_ensure_monitor"):
        instance.initialize()
        if instance._redis is None:
            pytest.fail("test Redis is not reachable")
        instance._redis.flushdb()
        yield instance
        instance._redis.flushdb()


@pytest.fixture
def restore_litellm_prices():
    saved = dict(litellm.model_cost[VERTEX])
    yield
    # Through register_model, which also resets the lookups litellm derives from it.
    litellm.register_model({VERTEX: saved})


def _request(*texts):
    return {
        "messages": [[{"role": "user", "content": text}] for text in texts],
        "max_tokens": None,
        "completions_per_prompt": 1,
    }


def _micro(spend, org_id=None) -> int:
    return int(spend._redis.get(day_key(module._utc_today(), org_id)) or 0)


def _spent(spend, usd, org_id=None):
    """Make *org_id* (or the platform alone) have spent *usd* today, as another process."""
    spend._redis.incrby(day_key(module._utc_today()), round(usd * MICRO_USD))
    if org_id:
        spend._redis.incrby(day_key(module._utc_today(), org_id), round(usd * MICRO_USD))


class TestPricing:
    def test_prices_come_from_litellm(self, spend):
        assert hosted_pricing.cost_usd(VERTEX, 1_000_000, 1_000_000) == pytest.approx(1.75)

    def test_unknown_model_counts_at_the_highest_default_output_rate(self, spend):
        assert hosted_pricing.cost_usd("vertex_ai/no-such", 1_000_000, 0) == pytest.approx(1.50)

    def test_input_estimate_counts_text_and_media(self):
        transcript = [
            {"role": "system", "content": "hello world"},
            {"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "image_url"}]},
        ]
        tokens = hosted_pricing.estimate_input_tokens(VERTEX, transcript)
        assert hosted_pricing.MEDIA_PART_TOKENS < tokens < hosted_pricing.MEDIA_PART_TOKENS + 20

    def test_a_long_transcript_is_estimated_without_the_tokenizer(self):
        chars = hosted_pricing.TOKENIZE_MAX_CHARS + 3
        transcript = [{"role": "user", "content": "x" * chars}]
        with patch.object(litellm, "token_counter") as counter:
            tokens = hosted_pricing.estimate_input_tokens(VERTEX, transcript)
        counter.assert_not_called()
        assert tokens == chars // hosted_pricing.CHARS_PER_TOKEN_ESTIMATE


class TestCallPath:
    def test_admit_and_record_make_no_redis_call(self, spend):
        spend._redis = MagicMock()
        spend.admit(VERTEX, _request("hello"), ORG)
        spend.record_output(VERTEX, 1000, ORG)
        spend.check_capacity(ORG)
        assert spend._redis.method_calls == []
        assert spend._pending_micro > 0
        assert spend._pending_org[ORG] == spend._pending_micro

    def test_admit_counts_the_input_before_the_call(self, spend):
        spend.admit(VERTEX, _request("word " * 1000), ORG)
        expected = hosted_pricing.cost_usd(
            VERTEX, litellm.token_counter(model=VERTEX, text="word " * 1000), 0
        )
        assert spend._pending_micro == pytest.approx(expected * MICRO_USD)

    def test_record_output_counts_only_the_output(self, spend):
        spend.record_output(VERTEX, 1_000_000, ORG)
        assert spend._pending_micro == round(ONE_M_OUTPUT_USD * MICRO_USD)

    def test_a_request_over_the_input_limit_is_refused_and_not_counted(self, spend, limits):
        limits(max_input=100)
        with pytest.raises(HostedRequestTooLarge) as exc:
            spend.admit(VERTEX, _request("short", "word " * 500), ORG)
        assert exc.value.http_status == 413
        assert spend._pending_micro == 0

    def test_off_without_a_budget(self, spend, limits):
        limits(platform=None)
        spend._capped = True
        spend.admit(VERTEX, _request("x" * 10_000_000), ORG)
        spend.record_output(VERTEX, 1_000_000, ORG)
        assert spend._pending_micro == 0


class TestSchemaAndBursts:
    def test_the_schema_counts_as_input_for_every_prompt(self, spend):
        schema = {
            "type": "object",
            "properties": {f"field_{i}": {"type": "string"} for i in range(200)},
        }
        request = {**_request("hi", "hi"), "response_format": schema}
        spend.admit(VERTEX, request, ORG)
        with_schema = spend._pending_micro
        spend._pending_micro = 0
        spend.admit(VERTEX, _request("hi", "hi"), ORG)
        assert with_schema > 10 * spend._pending_micro

    def test_a_huge_schema_is_refused(self, spend, limits):
        limits(max_input=100)
        request = {**_request("hi"), "response_format": {"description": "word " * 500}}
        with pytest.raises(HostedRequestTooLarge):
            spend.admit(VERTEX, request, ORG)

    def test_a_burst_in_this_process_is_refused_before_the_next_tick(self, spend, limits):
        limits(platform=10.0, org=2.0)
        spend.tick()  # reads the caps
        spend.record_output(VERTEX, 1_000_000, ORG)  # 1.50, not flushed
        spend.admit(VERTEX, _request("hi"), ORG)
        spend.record_output(VERTEX, 500_000, ORG)  # 2.25 now, still not flushed
        with pytest.raises(HostedModelOrgCapReached):
            spend.admit(VERTEX, _request("hi"), ORG)
        spend.admit(VERTEX, _request("hi"), OTHER_ORG)

    def test_a_platform_burst_is_refused_before_the_next_tick(self, spend):
        spend.tick()
        spend.record_output(VERTEX, 7_000_000, None)  # 10.50 of 10, not flushed
        with pytest.raises(HostedModelCapReached):
            spend.check_capacity(None)

    def test_record_input_counts_embeddings(self, spend):
        spend.record_input("vertex_ai/text-embedding-005", "word " * 1000, ORG)
        assert spend._pending_org[ORG] > 0


class TestPlatformCap:
    def test_flushes_pending_spend_to_the_day_counters(self, spend):
        spend.record_output(VERTEX, 1_000_000, ORG)
        spend.record_output(VERTEX, 1_000_000, None)
        spend.tick()
        assert _micro(spend) == round(2 * ONE_M_OUTPUT_USD * MICRO_USD)
        assert _micro(spend, ORG) == round(ONE_M_OUTPUT_USD * MICRO_USD)
        assert spend._redis.ttl(day_key(module._utc_today())) > 0
        assert spend._pending_micro < 1 and all(v < 1 for v in spend._pending_org.values())

    def test_fractions_of_a_micro_dollar_are_kept_until_they_add_up(self, spend):
        for _ in range(3):
            spend._add(None, 0.4 / MICRO_USD)  # 0.4 micro-dollars each
            spend.tick()
        assert _micro(spend) == 1
        assert spend._pending_micro == pytest.approx(0.2)

    def test_below_the_cap_calls_pass(self, spend):
        _spent(spend, 9.99)
        spend.tick()
        spend.admit(VERTEX, _request("hi"), ORG)

    def test_at_the_cap_calls_are_refused(self, spend):
        _spent(spend, 10)
        spend.tick()
        with pytest.raises(HostedModelCapReached) as exc:
            spend.admit(VERTEX, _request("hi"), ORG)
        assert str(exc.value) == CAP_REACHED_MESSAGE
        assert not hasattr(exc.value, "status_code")

    def test_a_new_process_knows_the_cap_is_reached_before_its_first_call(self, spend):
        _spent(spend, 10)
        fresh = HostedSpend()
        with patch.object(fresh, "_ensure_monitor"):
            fresh.start()
            with pytest.raises(HostedModelCapReached):
                fresh.check_capacity(None)

    def test_counts_from_other_processes_add_up(self, spend):
        other = HostedSpend()
        with patch.object(other, "_ensure_monitor"):
            other.record_output(VERTEX, 4_000_000, None)  # 6.00
            other.tick()
        spend.record_output(VERTEX, 3_000_000, None)  # 4.50
        spend.tick()
        with pytest.raises(HostedModelCapReached):
            spend.check_capacity(None)

    def test_redis_override_raises_the_cap(self, spend):
        _spent(spend, 10)
        spend._redis.set(CAP_OVERRIDE_KEY, "250")
        spend.tick()
        spend.check_capacity(None)

    def test_override_zero_refuses_everything(self, spend):
        spend._redis.set(CAP_OVERRIDE_KEY, "0")
        spend.tick()
        with pytest.raises(HostedModelCapReached):
            spend.check_capacity(None)

    def test_deleting_the_override_goes_back_to_the_env_cap(self, spend):
        spend._redis.set(CAP_OVERRIDE_KEY, "0")
        spend.tick()
        spend._redis.delete(CAP_OVERRIDE_KEY)
        spend.tick()
        spend.check_capacity(None)

    def test_unreadable_override_falls_back_to_the_env_cap(self, spend):
        spend._redis.set(CAP_OVERRIDE_KEY, "lots")
        spend.tick()
        spend.check_capacity(None)

    def test_unreachable_redis_lets_calls_through_and_keeps_the_count(self, spend):
        spend._capped = True
        spend._capped_orgs = {ORG}
        spend.record_output(VERTEX, 1_000_000, ORG)
        pending, pending_org = spend._pending_micro, dict(spend._pending_org)
        broken = MagicMock()
        broken.pipeline.return_value.execute.side_effect = ConnectionError("down")
        spend._redis = broken
        spend.tick()
        spend.check_capacity(ORG)
        assert spend._pending_micro == pending
        assert spend._pending_org == pending_org

    def test_each_threshold_is_logged_once_a_day(self, spend, caplog):
        _spent(spend, 9)
        with caplog.at_level(logging.WARNING, logger=module.__name__):
            spend.tick()
            spend.tick()
            _spent(spend, 1)
            spend.tick()
            spend.tick()
        markers = [r.usage_marker for r in caplog.records if hasattr(r, "usage_marker")]
        assert markers == [THRESHOLD_MARKER, CAP_REACHED_MARKER]


class TestOrgCap:
    def test_an_org_at_its_cap_is_refused_and_others_are_not(self, spend, limits):
        limits(org=2.0)
        spend.record_output(VERTEX, 1_000_000, ORG)  # first seen in this process
        spend.record_output(VERTEX, 1_000_000, OTHER_ORG)
        _spent(spend, 0.6, ORG)  # 1.50 + 0.60 >= 2.00
        spend.tick()
        with pytest.raises(HostedModelOrgCapReached) as exc:
            spend.admit(VERTEX, _request("hi"), ORG)
        assert str(exc.value) == ORG_CAP_REACHED_MESSAGE
        spend.admit(VERTEX, _request("hi"), OTHER_ORG)
        spend.admit(VERTEX, _request("hi"), None)

    def test_spend_from_other_processes_counts_toward_an_org(self, spend, limits):
        limits(org=2.0)
        other = HostedSpend()
        with patch.object(other, "_ensure_monitor"):
            other.record_output(VERTEX, 1_000_000, ORG)
            other.tick()
        spend.record_output(VERTEX, 1_000_000, ORG)
        spend.tick()
        with pytest.raises(HostedModelOrgCapReached):
            spend.check_capacity(ORG)

    def test_a_per_org_override_wins(self, spend, limits):
        limits(org=2.0)
        spend._redis.set(f"{ORG_CAP_OVERRIDE_KEY}:{ORG}", "50")
        spend.record_output(VERTEX, 2_000_000, ORG)  # 3.00
        spend.tick()
        spend.check_capacity(ORG)

    def test_an_override_for_all_orgs(self, spend, limits):
        limits(org=None)
        spend._redis.set(ORG_CAP_OVERRIDE_KEY, "1")
        spend.record_output(VERTEX, 1_000_000, ORG)  # 1.50
        spend.tick()
        with pytest.raises(HostedModelOrgCapReached):
            spend.check_capacity(ORG)

    def test_an_org_first_seen_in_a_check_is_read_on_the_next_tick(self, spend, limits):
        """An API pod refuses a run for an org whose spend happened in the workers."""
        limits(org=2.0)
        _spent(spend, 2.0, ORG)
        spend.check_capacity(ORG)  # nothing known about ORG yet in this process
        spend.tick()
        with pytest.raises(HostedModelOrgCapReached):
            spend.check_capacity(ORG)

    def test_no_org_cap_by_default(self, spend):
        spend.record_output(VERTEX, 5_000_000, ORG)  # 7.50 of the platform's 10
        spend.tick()
        spend.check_capacity(ORG)

    def test_reaching_it_is_logged_once(self, spend, limits, caplog):
        limits(org=1.0)
        spend.record_output(VERTEX, 1_000_000, ORG)
        with caplog.at_level(logging.WARNING, logger=module.__name__):
            spend.tick()
            spend.tick()
        markers = [r.usage_marker for r in caplog.records if hasattr(r, "usage_marker")]
        assert markers == [ORG_CAP_REACHED_MARKER]


class TestFork:
    def test_a_forked_child_starts_clean(self, spend):
        spend.record_output(VERTEX, 1_000_000, ORG)
        spend._lock.acquire()  # held by the parent's monitor at the moment of the fork
        spend._after_fork()
        assert spend._lock.acquire(blocking=False)
        spend._lock.release()
        assert spend._pending_micro == 0 and spend._pending_org == {}
        assert spend._redis is None and spend._monitor is None
        spend.initialize()  # the child connects on its own; the fixture needs it to clean up
        assert spend._redis is not None


class TestPrices:
    def test_refresh_stores_only_our_default_models(self, spend, restore_litellm_prices):
        fetched = {
            VERTEX: {**litellm.model_cost[VERTEX]},
            "openai/gpt-4o": {"output_cost_per_token": 1e-5},
        }
        with patch.object(litellm, "get_model_cost_map", return_value=fetched):
            assert spend.refresh_prices() == 1
        stored = json.loads(spend._redis.get(PRICES_KEY))
        assert set(stored["models"]) == {VERTEX}
        assert stored["fetched_at"]

    def test_refresh_does_nothing_without_a_budget(self, spend, limits):
        limits(platform=None)
        with patch.object(litellm, "get_model_cost_map") as fetch:
            assert spend.refresh_prices() == 0
        fetch.assert_not_called()

    def test_a_price_in_redis_reprices_the_next_call(self, spend, restore_litellm_prices):
        entry = {
            **litellm.model_cost[VERTEX],
            "input_cost_per_token": 1e-6,
            "output_cost_per_token": 2e-6,
        }
        spend._redis.set(PRICES_KEY, json.dumps({"models": {VERTEX: entry}}))
        spend.tick()
        assert hosted_pricing.cost_usd(VERTEX, 1_000_000, 1_000_000) == pytest.approx(3.0)

    def test_without_redis_prices_litellm_startup_prices_apply(self, spend):
        spend.tick()
        assert hosted_pricing.cost_usd(VERTEX, 1_000_000, 0) == pytest.approx(0.25)


class TestSdkWiring:
    @pytest.fixture
    def recorded(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            usage_tracking.hosted_spend, "record_output", lambda *args: calls.append(args)
        )
        monkeypatch.setattr(usage_tracking, "dispatch_accrual", lambda *a, **k: None)
        return calls

    @staticmethod
    def _model(metered):
        model = LiteLLM(VERTEX)
        model.usage_metered = metered
        return model

    def test_metered_output_is_counted_even_without_an_org(self, recorded):
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        usage_tracking.accrue_model_tokens(usage, self._model(True))
        assert recorded == [(VERTEX, 5, None)]

    def test_unstamped_models_are_counted(self, recorded):
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        usage_tracking.accrue_model_tokens(usage, self._model(None))
        assert recorded == [(VERTEX, 5, None)]

    def test_an_orgs_own_key_is_not_counted(self, recorded):
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        usage_tracking.accrue_model_tokens(usage, self._model(False))
        assert recorded == []

    def test_precall_check_admits_every_model_but_an_orgs_own(self, monkeypatch):
        admitted = []
        monkeypatch.setattr(
            usage_tracking.hosted_spend, "admit", lambda *args: admitted.append(args)
        )
        request = _request("hi")
        usage_tracking.check_hosted_spend(self._model(False), request)
        usage_tracking.check_hosted_spend(self._model(True), request, organization_id=ORG)
        usage_tracking.check_hosted_spend(self._model(None), request, organization_id=ORG)
        assert admitted == [(VERTEX, request, ORG), (VERTEX, request, ORG)]

    def test_without_a_request_it_only_checks_capacity(self, monkeypatch):
        checked = []
        monkeypatch.setattr(usage_tracking.hosted_spend, "check_capacity", checked.append)
        usage_tracking.check_hosted_spend(self._model(True), organization_id=ORG)
        assert checked == [ORG]

    def test_install_registers_the_precall_check(self):
        from rhesis.sdk.models import get_default_precall_check

        usage_tracking.install_usage_sink()
        try:
            assert get_default_precall_check() is usage_tracking.check_hosted_spend
        finally:
            usage_tracking.uninstall_usage_sink()


class TestErrorSurfaces:
    @pytest.mark.parametrize(
        "refusal",
        [HostedModelCapReached(), HostedModelOrgCapReached(), HostedRequestTooLarge(9, 1)],
    )
    def test_every_refusal_keeps_its_message_and_is_not_retried(self, refusal):
        assert stream_error_message(refusal) == str(refusal)
        assert not _is_retriable_failure(_failure_result("t1", refusal, 1.0))

    def test_celery_does_not_autoretry(self):
        assert ModelCallRefused in BaseJob.dont_autoretry_for

    def test_a_refusal_relayed_through_the_rhesis_model_is_not_retried(self):
        relayed = PlatformRefusedCall("Daily capacity.", "hosted_model_at_capacity", 503)
        assert not _is_retriable_failure(_failure_result("t1", relayed, 1.0))

    def test_internal_error_lets_a_wrapped_refusal_through(self):
        try:
            try:
                raise HostedModelCapReached()
            except HostedModelCapReached as cause:
                raise RuntimeError("synthesis failed") from cause
        except RuntimeError as wrapped:
            with pytest.raises(HostedModelCapReached):
                internal_error(wrapped, context="generating metric", status_code=400)

    def test_handle_database_exceptions_lets_a_refusal_through(self):
        @handle_database_exceptions(entity_name="metric")
        def route():
            raise RuntimeError("model failed") from HostedModelOrgCapReached()

        with pytest.raises(HostedModelOrgCapReached):
            route()

    def test_seconds_until_reset_is_within_a_day(self):
        assert 0 < seconds_until_reset() <= 24 * 3600

    def test_embedding_route_is_capped(self, authenticated_client, spend, monkeypatch):
        embedder = MagicMock(model_name="vertex_ai/text-embedding-005")
        embedder.generate.return_value = [0.1, 0.2]
        monkeypatch.setattr(
            "rhesis.backend.app.utils.user_model_utils.resolve_embedder", lambda *a, **k: embedder
        )
        monkeypatch.setattr(
            hosted_pricing,
            "get_model_settings",
            lambda: SimpleNamespace(embedding_model="vertex_ai/text-embedding-005"),
        )
        monkeypatch.setattr("rhesis.backend.app.routers.services.hosted_spend", spend)

        ok = authenticated_client.post("/services/generate/embedding", json={"text": "hello"})
        assert ok.status_code == 200, ok.text
        assert sum(spend._pending_org.values()) > 0

        spend._capped = True
        capped = authenticated_client.post("/services/generate/embedding", json={"text": "hi"})
        assert capped.status_code == 503
        assert capped.json()["error"] == "hosted_model_at_capacity"

    def test_oversized_embedding_text_and_schema_are_rejected(self, authenticated_client):
        too_long = authenticated_client.post(
            "/services/generate/embedding", json={"text": "x" * 50_001}
        )
        assert too_long.status_code == 422
        schema = {"description": "x" * 100_001}
        huge = authenticated_client.post(
            "/services/generate/content", json={"prompt": "hi", "schema": schema}
        )
        assert huge.status_code == 422

    @pytest.mark.parametrize(
        "refusal, status, code, retry_after",
        [
            (HostedModelCapReached(), 503, "hosted_model_at_capacity", True),
            (HostedModelOrgCapReached(), 503, "hosted_model_org_daily_limit", True),
            (HostedRequestTooLarge(300_000, 200_000), 413, "hosted_model_request_too_large", False),
        ],
    )
    def test_generate_content_answers_each_refusal(
        self, authenticated_client, refusal, status, code, retry_after
    ):
        with patch(
            "rhesis.backend.app.routers.services._resolve_content_generation_model",
            side_effect=refusal,
        ):
            response = authenticated_client.post(
                "/services/generate/content", json={"prompt": "hi"}
            )
        assert response.status_code == status
        assert response.json() == {"error": code, "message": str(refusal)}
        assert ("Retry-After" in response.headers) is retry_after
