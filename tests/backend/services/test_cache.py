"""Unit tests for RedisBackedCache."""

from unittest.mock import MagicMock, patch

import pytest

from rhesis.backend.app.services.cache import RedisBackedCache


class _ConcreteCache(RedisBackedCache):
    """Concrete subclass for testing the RedisBackedCache base."""


@pytest.mark.unit
class TestRedisBackedCacheInMemory:
    """Tests for in-memory fallback behavior."""

    def test_initialize_without_redis(self):
        with patch("redis.Redis.from_url", side_effect=ConnectionError("unavailable")):
            cache = _ConcreteCache(redis_db=7, cache_name="test", ttl=60)
            cache.initialize()

        assert cache._using_redis is False
        assert cache._initialized is True

    def test_set_and_get(self):
        with patch("redis.Redis.from_url", side_effect=ConnectionError("unavailable")):
            cache = _ConcreteCache(redis_db=0, cache_name="test", ttl=120)
            cache.initialize()

        cache._set("k1", "v1")
        assert cache._get("k1") == "v1"

    def test_get_missing_key(self):
        with patch("redis.Redis.from_url", side_effect=ConnectionError("unavailable")):
            cache = _ConcreteCache(redis_db=0, cache_name="test", ttl=120)
            cache.initialize()

        assert cache._get("missing") is None

    def test_delete(self):
        with patch("redis.Redis.from_url", side_effect=ConnectionError("unavailable")):
            cache = _ConcreteCache(redis_db=0, cache_name="test", ttl=120)
            cache.initialize()

        cache._set("k", "v")
        cache._delete("k")
        assert cache._get("k") is None

    def test_mget(self):
        with patch("redis.Redis.from_url", side_effect=ConnectionError("unavailable")):
            cache = _ConcreteCache(redis_db=0, cache_name="test", ttl=120)
            cache.initialize()

        cache._set("a", "1")
        cache._set("b", "2")
        assert cache._mget(["a", "b", "c"]) == ["1", "2", None]

    def test_pipeline_set(self):
        with patch("redis.Redis.from_url", side_effect=ConnectionError("unavailable")):
            cache = _ConcreteCache(redis_db=0, cache_name="test", ttl=120)
            cache.initialize()

        cache._pipeline_set({"x": "10", "y": "20"})
        assert cache._get("x") == "10"
        assert cache._get("y") == "20"

    def test_getdel(self):
        with patch("redis.Redis.from_url", side_effect=ConnectionError("unavailable")):
            cache = _ConcreteCache(redis_db=0, cache_name="test", ttl=120)
            cache.initialize()

        cache._set("g", "once")
        assert cache._getdel("g") == "once"
        assert cache._getdel("g") is None

    def test_ttl_eviction(self):
        cache = _ConcreteCache(redis_db=0, cache_name="test", ttl=30)
        t = {"v": 1000.0}

        def fake_monotonic():
            return t["v"]

        with patch("redis.Redis.from_url", side_effect=ConnectionError("unavailable")):
            with patch(
                "rhesis.backend.app.services.cache.time.monotonic",
                side_effect=fake_monotonic,
            ):
                cache.initialize()
                cache._set("stale", "x")

        t["v"] = 1000.0 + 31.0
        with patch("rhesis.backend.app.services.cache.time.monotonic", side_effect=fake_monotonic):
            assert cache._get("stale") is None


@pytest.mark.unit
class TestRedisBackedCacheWithMockRedis:
    """Tests with a mocked Redis client."""

    def test_initialize_with_redis(self):
        mock_client = MagicMock()
        mock_client.ping.return_value = True

        with patch("redis.Redis.from_url", return_value=mock_client) as from_url:
            cache = _ConcreteCache(redis_db=3, cache_name="redis-test", ttl=90)
            cache.initialize()

        assert cache._using_redis is True
        assert cache._initialized is True
        from_url.assert_called_once()
        mock_client.ping.assert_called_once()

    def test_set_calls_redis(self):
        mock_client = MagicMock()
        mock_client.ping.return_value = True

        with patch("redis.Redis.from_url", return_value=mock_client):
            cache = _ConcreteCache(redis_db=1, cache_name="c", ttl=120)
            cache.initialize()

        cache._set("key1", "val1")
        mock_client.set.assert_called_with("key1", "val1", ex=120)

        cache._set("key2", "val2", ttl=10)
        mock_client.set.assert_called_with("key2", "val2", ex=10)

    def test_get_calls_redis(self):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.get.return_value = "from-redis"

        with patch("redis.Redis.from_url", return_value=mock_client):
            cache = _ConcreteCache(redis_db=1, cache_name="c", ttl=120)
            cache.initialize()

        assert cache._get("rk") == "from-redis"
        mock_client.get.assert_called_once_with("rk")

    def test_delete_calls_redis(self):
        mock_client = MagicMock()
        mock_client.ping.return_value = True

        with patch("redis.Redis.from_url", return_value=mock_client):
            cache = _ConcreteCache(redis_db=1, cache_name="c", ttl=120)
            cache.initialize()

        cache._delete("d1", "d2")
        mock_client.delete.assert_called_once_with("d1", "d2")

    def test_mget_calls_redis(self):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.mget.return_value = ["a", None, "c"]

        with patch("redis.Redis.from_url", return_value=mock_client):
            cache = _ConcreteCache(redis_db=1, cache_name="c", ttl=120)
            cache.initialize()

        keys = ["k1", "k2", "k3"]
        assert cache._mget(keys) == ["a", None, "c"]
        mock_client.mget.assert_called_once_with(keys)

    def test_pipeline_set_calls_redis(self):
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        pipe = MagicMock()
        mock_client.pipeline.return_value = pipe

        with patch("redis.Redis.from_url", return_value=mock_client):
            cache = _ConcreteCache(redis_db=1, cache_name="c", ttl=55)
            cache.initialize()

        cache._pipeline_set({"p1": "v1", "p2": "v2"}, ttl=99)

        mock_client.pipeline.assert_called_once()
        pipe.set.assert_any_call("p1", "v1", ex=99)
        pipe.set.assert_any_call("p2", "v2", ex=99)
        pipe.execute.assert_called_once()

    def test_redis_failure_falls_back_to_memory(self):
        mock_client = MagicMock()
        mock_client.ping.return_value = True

        with patch("redis.Redis.from_url", return_value=mock_client):
            cache = _ConcreteCache(redis_db=1, cache_name="c", ttl=120)
            cache.initialize()

        failing = MagicMock()
        failing.set.side_effect = RuntimeError("redis down")
        failing.get.side_effect = RuntimeError("redis down")
        cache._redis = failing
        cache._redis_read = failing

        cache._set("memk", "memv")
        assert cache._get("memk") == "memv"


@pytest.mark.unit
class TestRedisBackedCacheReadReplica:
    """Tests for BROKER_READ_URL read replica routing."""

    def test_separate_read_client_when_broker_read_url_set(self):
        write_client = MagicMock()
        write_client.ping.return_value = True
        read_client = MagicMock()
        read_client.ping.return_value = True

        clients = iter([write_client, read_client])

        with (
            patch("redis.Redis.from_url", side_effect=lambda *a, **kw: next(clients)),
            patch.dict("os.environ", {"BROKER_READ_URL": "redis://replica:6379/0"}),
        ):
            cache = _ConcreteCache(redis_db=1, cache_name="rr", ttl=60)
            cache.initialize()

        assert cache._redis is write_client
        assert cache._redis_read is read_client
        assert cache._has_separate_read is True

    def test_reads_go_to_read_client_writes_to_primary(self):
        write_client = MagicMock()
        write_client.ping.return_value = True
        read_client = MagicMock()
        read_client.ping.return_value = True
        read_client.get.return_value = "from-replica"
        read_client.mget.return_value = ["a", "b"]

        clients = iter([write_client, read_client])

        with (
            patch("redis.Redis.from_url", side_effect=lambda *a, **kw: next(clients)),
            patch.dict("os.environ", {"BROKER_READ_URL": "redis://replica:6379/0"}),
        ):
            cache = _ConcreteCache(redis_db=1, cache_name="rr", ttl=60)
            cache.initialize()

        assert cache._get("k") == "from-replica"
        read_client.get.assert_called_once_with("k")
        write_client.get.assert_not_called()

        assert cache._mget(["a", "b"]) == ["a", "b"]
        read_client.mget.assert_called_once_with(["a", "b"])
        write_client.mget.assert_not_called()

        cache._set("w", "v")
        write_client.set.assert_called_once_with("w", "v", ex=60)
        read_client.set.assert_not_called()

        cache._delete("d")
        write_client.delete.assert_called_once_with("d")
        read_client.delete.assert_not_called()

    def test_read_replica_failure_at_init_falls_back_to_primary(self):
        write_client = MagicMock()
        write_client.ping.return_value = True
        write_client.get.return_value = "from-primary"

        call_count = {"n": 0}

        def from_url_side_effect(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return write_client
            raise ConnectionError("replica unreachable")

        with (
            patch("redis.Redis.from_url", side_effect=from_url_side_effect),
            patch.dict("os.environ", {"BROKER_READ_URL": "redis://bad-replica:6379/0"}),
        ):
            cache = _ConcreteCache(redis_db=1, cache_name="rr", ttl=60)
            cache.initialize()

        assert cache._redis is write_client
        assert cache._redis_read is write_client
        assert cache._has_separate_read is False
        assert cache._get("k") == "from-primary"

    def test_get_replica_failure_retries_primary(self):
        write_client = MagicMock()
        write_client.ping.return_value = True
        write_client.get.return_value = "from-primary"
        read_client = MagicMock()
        read_client.ping.return_value = True
        read_client.get.side_effect = ConnectionError("replica down")

        clients = iter([write_client, read_client])

        with (
            patch("redis.Redis.from_url", side_effect=lambda *a, **kw: next(clients)),
            patch.dict("os.environ", {"BROKER_READ_URL": "redis://replica:6379/0"}),
        ):
            cache = _ConcreteCache(redis_db=1, cache_name="rr", ttl=60)
            cache.initialize()

        assert cache._has_separate_read is True
        result = cache._get("k")
        assert result == "from-primary"
        assert cache._has_separate_read is False
        assert cache._redis_read is write_client
        write_client.get.assert_called_once_with("k")

    def test_mget_replica_failure_retries_primary(self):
        write_client = MagicMock()
        write_client.ping.return_value = True
        write_client.mget.return_value = ["v1", "v2"]
        read_client = MagicMock()
        read_client.ping.return_value = True
        read_client.mget.side_effect = ConnectionError("replica down")

        clients = iter([write_client, read_client])

        with (
            patch("redis.Redis.from_url", side_effect=lambda *a, **kw: next(clients)),
            patch.dict("os.environ", {"BROKER_READ_URL": "redis://replica:6379/0"}),
        ):
            cache = _ConcreteCache(redis_db=1, cache_name="rr", ttl=60)
            cache.initialize()

        assert cache._has_separate_read is True
        result = cache._mget(["a", "b"])
        assert result == ["v1", "v2"]
        assert cache._has_separate_read is False
        write_client.mget.assert_called_once_with(["a", "b"])

    def test_close_with_separate_read_client(self):
        write_client = MagicMock()
        write_client.ping.return_value = True
        read_client = MagicMock()
        read_client.ping.return_value = True

        clients = iter([write_client, read_client])

        with (
            patch("redis.Redis.from_url", side_effect=lambda *a, **kw: next(clients)),
            patch.dict("os.environ", {"BROKER_READ_URL": "redis://replica:6379/0"}),
        ):
            cache = _ConcreteCache(redis_db=1, cache_name="rr", ttl=60)
            cache.initialize()

        cache.close()

        write_client.close.assert_called_once()
        read_client.close.assert_called_once()
        assert cache._redis is None
        assert cache._redis_read is None
        assert cache._has_separate_read is False
