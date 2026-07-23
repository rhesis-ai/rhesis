"""Unit tests for GarakProbeCache."""

import json
from unittest.mock import AsyncMock

import pytest

from rhesis.backend.app.services.garak.cache import GarakProbeCache


@pytest.fixture(autouse=True)
def _reset_garak_cache():
    """Reset class-level state between tests."""
    GarakProbeCache._redis_client = None
    GarakProbeCache._redis_read_client = None
    GarakProbeCache._has_separate_read = False
    GarakProbeCache._initialized = False
    GarakProbeCache._memory_cache.clear()
    yield
    GarakProbeCache._redis_client = None
    GarakProbeCache._redis_read_client = None
    GarakProbeCache._has_separate_read = False
    GarakProbeCache._initialized = False
    GarakProbeCache._memory_cache.clear()


def _cached_json(schema_version=GarakProbeCache.SCHEMA_VERSION):
    """Return a JSON string matching the expected cache format."""
    return json.dumps(
        {
            "modules": [],
            "probes_by_module": {},
            "schema_version": schema_version,
        }
    )


@pytest.mark.unit
class TestGarakProbeCacheReadReplicaRuntime:
    """Tests for runtime read-replica failure + retry-against-primary."""

    @pytest.mark.asyncio
    async def test_get_retries_primary_on_replica_failure(self):
        primary = AsyncMock()
        replica = AsyncMock()
        replica.get.side_effect = ConnectionError("replica down")
        primary.get.return_value = _cached_json()

        GarakProbeCache._redis_client = primary
        GarakProbeCache._redis_read_client = replica
        GarakProbeCache._has_separate_read = True
        GarakProbeCache._initialized = True

        result = await GarakProbeCache.get("0.1.0")

        assert result is not None
        assert result["schema_version"] == GarakProbeCache.SCHEMA_VERSION
        assert GarakProbeCache._has_separate_read is False
        assert GarakProbeCache._redis_read_client is primary
        primary.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_returns_none_when_both_fail(self):
        primary = AsyncMock()
        replica = AsyncMock()
        replica.get.side_effect = ConnectionError("replica down")
        primary.get.side_effect = ConnectionError("primary down too")

        GarakProbeCache._redis_client = primary
        GarakProbeCache._redis_read_client = replica
        GarakProbeCache._has_separate_read = True
        GarakProbeCache._initialized = True

        result = await GarakProbeCache.get("0.1.0")

        assert result is None
        assert GarakProbeCache._has_separate_read is False

    @pytest.mark.asyncio
    async def test_get_skips_stale_schema_on_primary_retry(self):
        primary = AsyncMock()
        replica = AsyncMock()
        replica.get.side_effect = ConnectionError("replica down")
        primary.get.return_value = _cached_json(schema_version=0)

        GarakProbeCache._redis_client = primary
        GarakProbeCache._redis_read_client = replica
        GarakProbeCache._has_separate_read = True
        GarakProbeCache._initialized = True

        result = await GarakProbeCache.get("0.1.0")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_disables_all_redis_when_primary_fails(self):
        primary = AsyncMock()
        primary.get.side_effect = OSError("primary gone")

        GarakProbeCache._redis_client = primary
        GarakProbeCache._redis_read_client = primary
        GarakProbeCache._has_separate_read = False
        GarakProbeCache._initialized = True

        result = await GarakProbeCache.get("0.1.0")

        assert result is None
        assert GarakProbeCache._redis_client is None

    @pytest.mark.asyncio
    async def test_get_populates_memory_on_primary_retry_hit(self):
        primary = AsyncMock()
        replica = AsyncMock()
        replica.get.side_effect = ConnectionError("replica down")
        primary.get.return_value = _cached_json()

        GarakProbeCache._redis_client = primary
        GarakProbeCache._redis_read_client = replica
        GarakProbeCache._has_separate_read = True
        GarakProbeCache._initialized = True

        cache_key = GarakProbeCache._cache_key("0.1.0")
        assert cache_key not in GarakProbeCache._memory_cache

        await GarakProbeCache.get("0.1.0")

        assert cache_key in GarakProbeCache._memory_cache
