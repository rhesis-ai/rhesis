"""TTLCache: per-process values that rarely change, loaded once per key and TTL."""

import threading
import time

import pytest

from rhesis.backend.app.utils.ttl_cache import TTLCache


@pytest.mark.unit
class TestTTLCache:
    def test_loads_once_within_the_ttl(self):
        cache = TTLCache(lambda: 60)
        calls = []

        for _ in range(3):
            assert cache.get_or_load("k", lambda: calls.append(1) or "v") == "v"

        assert len(calls) == 1

    def test_keys_are_separate(self):
        cache = TTLCache(lambda: 60)

        assert cache.get_or_load(("org-a", "p"), lambda: "a") == "a"
        assert cache.get_or_load(("org-b", "p"), lambda: "b") == "b"

    def test_an_expired_value_is_loaded_again(self):
        ttl = {"s": 0.01}
        cache = TTLCache(lambda: ttl["s"])
        cache.get_or_load("k", lambda: "old")
        time.sleep(0.02)

        assert cache.get_or_load("k", lambda: "new") == "new"

    def test_zero_ttl_never_caches(self):
        cache = TTLCache(lambda: 0)
        cache.get_or_load("k", lambda: "first")

        assert cache.get_or_load("k", lambda: "second") == "second"

    def test_a_failed_load_is_not_cached(self):
        cache = TTLCache(lambda: 60)

        def boom():
            raise RuntimeError("db down")

        with pytest.raises(RuntimeError):
            cache.get_or_load("k", boom)
        assert cache.get_or_load("k", lambda: "v") == "v"

    def test_threads_missing_together_load_once(self):
        # Every worker thread misses when an entry expires; one load must serve them all.
        cache = TTLCache(lambda: 60)
        calls = []
        start = threading.Barrier(16)

        def load():
            calls.append(1)
            time.sleep(0.05)
            return "v"

        results = []

        def worker():
            start.wait()
            results.append(cache.get_or_load("k", load))

        threads = [threading.Thread(target=worker) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results == ["v"] * 16
        assert len(calls) == 1

    def test_it_keeps_no_state_for_expired_or_finished_keys(self):
        ttl = {"s": 0.01}
        cache = TTLCache(lambda: ttl["s"])
        for key in range(50):
            cache.get_or_load(key, lambda: "v")
        time.sleep(0.02)

        cache.get_or_load("live", lambda: "v")

        assert list(cache._values) == ["live"]
        assert cache._loading == {}
