"""
Garak probe cache using Redis with memory fallback.

This module implements a two-level cache for Garak probe data:
- L1: In-memory cache (class-level, shared across instances within a process)
- L2: Redis cache (shared across pods, survives restarts)

The cache is version-aware: keys include the garak version, so upgrading
garak automatically invalidates the cache.
"""

import json
import os
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import redis.asyncio as redis

from rhesis.backend.logging.rhesis_logger import logger


class GarakProbeCache:
    """
    Two-level cache: Memory (L1) + Redis (L2) for Garak probe data.

    This cache eliminates the need to re-enumerate Garak probes on every
    API request. The first request (or startup pre-warming) generates the
    cache, and subsequent requests read from memory or Redis.

    Usage:
        await GarakProbeCache.initialize()
        data = await GarakProbeCache.get(garak_version)
        if not data:
            data = generate_probe_data()
            await GarakProbeCache.set(garak_version, data)
    """

    CACHE_KEY_PREFIX = "garak:probes"
    CACHE_TTL = 86400 * 7  # 7 days - probes rarely change within a version
    SCHEMA_VERSION = 1  # Increment when changing extraction logic

    # Class-level memory cache (shared across instances within a process)
    _memory_cache: ClassVar[Dict[str, Dict]] = {}
    _redis_client: ClassVar[Optional[redis.Redis]] = None
    _initialized: ClassVar[bool] = False

    @classmethod
    async def initialize(cls) -> None:
        """
        Initialize Redis connection for caching.

        Uses Redis database 2 to avoid conflicts with Celery (db 0 and 1).
        Fails gracefully if Redis is unavailable - the cache will operate
        in memory-only mode.
        """
        if cls._initialized:
            return

        try:
            redis_url = os.getenv("BROKER_URL", "redis://localhost:6379/0")
            # Use database 2 for application cache (0 and 1 are for Celery)
            # Parse URL properly to handle cases where BROKER_URL has no database suffix
            parsed = urlparse(redis_url)
            cache_url = urlunparse(parsed._replace(path="/2"))
            cls._redis_client = await redis.from_url(
                cache_url,
                decode_responses=True,
                encoding="utf-8",
                socket_connect_timeout=5,  # Don't hang forever on connect
                socket_timeout=5,  # Don't hang forever on operations
            )
            # Test connection - this will raise if Redis is not available
            await cls._redis_client.ping()
            cls._initialized = True
            logger.info("Garak probe cache: Redis connection established (db 2)")
        except Exception as e:
            # Log at debug level to avoid noise when Redis is intentionally not running
            logger.debug(
                f"Garak probe cache: Redis not available ({type(e).__name__}: {e}). "
                "Operating in memory-only mode."
            )
            cls._redis_client = None
            cls._initialized = True  # Mark as initialized even without Redis

    @classmethod
    async def _disable_redis(cls) -> None:
        """Disable Redis client after a connection failure."""
        if cls._redis_client:
            try:
                await cls._redis_client.close()
            except Exception:
                pass
            cls._redis_client = None
            logger.debug("Garak probe cache: Redis disabled due to connection failure")

    @classmethod
    async def close(cls) -> None:
        """Close Redis connection if open."""
        if cls._redis_client:
            await cls._redis_client.close()
            cls._redis_client = None
            cls._initialized = False
            logger.info("Garak probe cache: Redis connection closed")

    @classmethod
    def _cache_key(cls, garak_version: str) -> str:
        """Generate cache key for a specific garak version."""
        return f"{cls.CACHE_KEY_PREFIX}:v{garak_version}:modules"

    @classmethod
    async def get(cls, garak_version: str) -> Optional[Dict[str, Any]]:
        """
        Get cached probe data, checking memory first then Redis.

        Args:
            garak_version: The installed garak version string

        Returns:
            Cached probe data dict, or None if not cached
        """
        cache_key = cls._cache_key(garak_version)

        # L1: Check memory cache first (fastest)
        if cache_key in cls._memory_cache:
            cached = cls._memory_cache[cache_key]
            if cached.get("schema_version") == cls.SCHEMA_VERSION:
                logger.debug(f"Garak probe cache HIT (memory): {cache_key}")
                return cached
            else:
                # Schema version mismatch - invalidate stale memory cache
                del cls._memory_cache[cache_key]

        # L2: Check Redis cache
        if cls._redis_client:
            try:
                data = await cls._redis_client.get(cache_key)
                if data:
                    parsed = json.loads(data)
                    if parsed.get("schema_version") == cls.SCHEMA_VERSION:
                        # Populate L1 cache from L2
                        cls._memory_cache[cache_key] = parsed
                        logger.debug(f"Garak probe cache HIT (Redis): {cache_key}")
                        return parsed
                    else:
                        # Schema version mismatch - delete stale Redis cache
                        await cls._redis_client.delete(cache_key)
            except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
                # Connection lost - disable Redis and continue with memory-only mode
                logger.debug(f"Garak probe cache: Redis connection lost ({e})")
                await cls._disable_redis()
            except Exception as e:
                # Other errors (e.g., JSON decode) - log but don't disable Redis
                logger.debug(f"Garak probe cache: Redis read error ({e})")

        # Cache miss - caller will log this at INFO level
        return None

    @classmethod
    async def set(cls, garak_version: str, data: Dict[str, Any]) -> None:
        """
        Store probe data in both memory and Redis caches.

        Args:
            garak_version: The installed garak version string
            data: The probe data to cache (modules, probes, metadata)
        """
        cache_key = cls._cache_key(garak_version)

        # Add cache metadata
        cache_data = {
            **data,
            "garak_version": garak_version,
            "schema_version": cls.SCHEMA_VERSION,
            "cached_at": datetime.utcnow().isoformat(),
        }

        # L1: Store in memory cache
        cls._memory_cache[cache_key] = cache_data

        # L2: Store in Redis cache
        if cls._redis_client:
            try:
                await cls._redis_client.setex(
                    cache_key,
                    cls.CACHE_TTL,
                    json.dumps(cache_data),
                )
                logger.debug(f"Garak probe cache stored in Redis: {cache_key}")
            except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
                # Connection lost - disable Redis and continue with memory-only mode
                logger.debug(f"Garak probe cache: Redis connection lost ({e})")
                await cls._disable_redis()
            except Exception as e:
                # Other errors - log but don't disable Redis
                logger.debug(f"Garak probe cache: Redis write error ({e})")

    @classmethod
    async def invalidate(cls, garak_version: Optional[str] = None) -> None:
        """
        Invalidate cache for a specific version or all versions.

        Args:
            garak_version: If provided, invalidate only this version.
                          If None, invalidate all cached versions.
        """
        if garak_version:
            cache_key = cls._cache_key(garak_version)
            cls._memory_cache.pop(cache_key, None)
            if cls._redis_client:
                try:
                    await cls._redis_client.delete(cache_key)
                    logger.info(f"Garak probe cache INVALIDATED: {cache_key}")
                except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
                    logger.debug(f"Garak probe cache: Redis connection lost ({e})")
                    await cls._disable_redis()
                except Exception as e:
                    logger.debug(f"Garak probe cache: Redis delete error ({e})")
        else:
            # Clear all Garak probe caches
            cls._memory_cache.clear()
            if cls._redis_client:
                try:
                    keys_deleted = 0
                    async for key in cls._redis_client.scan_iter(f"{cls.CACHE_KEY_PREFIX}:*"):
                        await cls._redis_client.delete(key)
                        keys_deleted += 1
                    logger.info(f"Garak probe cache INVALIDATED ALL: {keys_deleted} keys")
                except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
                    logger.debug(f"Garak probe cache: Redis connection lost ({e})")
                    await cls._disable_redis()
                except Exception as e:
                    logger.debug(f"Garak probe cache: Redis clear error ({e})")

    @classmethod
    def is_redis_available(cls) -> bool:
        """Check if Redis is available for caching."""
        return cls._redis_client is not None

    @classmethod
    async def get_cache_info(cls, garak_version: str) -> Dict[str, Any]:
        """
        Get information about the cache state for debugging.

        Args:
            garak_version: The garak version to check

        Returns:
            Dict with cache status information
        """
        cache_key = cls._cache_key(garak_version)
        info = {
            "cache_key": cache_key,
            "redis_available": cls.is_redis_available(),
            "in_memory": cache_key in cls._memory_cache,
            "in_redis": False,
            "schema_version": cls.SCHEMA_VERSION,
        }

        if cls._redis_client:
            try:
                exists = await cls._redis_client.exists(cache_key)
                info["in_redis"] = bool(exists)
                if exists:
                    ttl = await cls._redis_client.ttl(cache_key)
                    info["redis_ttl_seconds"] = ttl
            except (redis.ConnectionError, redis.TimeoutError, OSError):
                # Connection lost - just report as unavailable
                info["redis_available"] = False
            except Exception:
                pass

        if cache_key in cls._memory_cache:
            cached = cls._memory_cache[cache_key]
            info["cached_at"] = cached.get("cached_at")
            info["module_count"] = len(cached.get("modules", []))

        return info


def serialize_probe_data(
    modules: List[Any], probes_by_module: Dict[str, List[Any]]
) -> Dict[str, Any]:
    """
    Serialize probe data for caching.

    Converts dataclass instances to dicts for JSON serialization.

    Args:
        modules: List of GarakModuleInfo dataclass instances
        probes_by_module: Dict mapping module names to lists of GarakProbeInfo

    Returns:
        Dict ready for JSON serialization
    """
    from dataclasses import asdict

    return {
        "modules": [asdict(m) for m in modules],
        "probes_by_module": {
            module_name: [asdict(p) for p in probes]
            for module_name, probes in probes_by_module.items()
        },
    }


def deserialize_probe_data(data: Dict[str, Any]) -> tuple:
    """
    Deserialize cached probe data back to dataclass instances.

    Args:
        data: Cached dict from Redis/memory

    Returns:
        Tuple of (modules, probes_by_module) with dataclass instances
    """
    from rhesis.backend.app.services.garak.probes import GarakModuleInfo, GarakProbeInfo

    modules = [GarakModuleInfo(**m) for m in data.get("modules", [])]

    probes_by_module = {
        module_name: [GarakProbeInfo(**p) for p in probes]
        for module_name, probes in data.get("probes_by_module", {}).items()
    }

    return modules, probes_by_module
