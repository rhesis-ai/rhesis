import json
import logging
import os
import time
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit

from redis.asyncio import Redis  # type: ignore[reportMissingImports]

logger = logging.getLogger(__name__)

CHATBOT_SESSIONS_DB = 4
SESSION_KEY_PREFIX = "chatbot:session:"


class SessionStore(Protocol):
    async def get(self, session_id: str) -> list[dict[str, Any]]:
        """Return messages for a session and refresh its TTL."""

    async def append(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """Append messages to a session and refresh its TTL."""

    async def exists(self, session_id: str) -> bool:
        """Return whether a session exists."""

    async def delete(self, session_id: str) -> bool:
        """Delete a session."""

    async def close(self) -> None:
        """Close store resources."""


class InMemorySessionStore:
    """Local development fallback used when BROKER_URL is not configured."""

    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, tuple[list[dict[str, Any]], float]] = {}

    def _expires_at(self) -> float:
        return time.time() + self.ttl_seconds

    def _purge_if_expired(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session and session[1] <= time.time():
            self._sessions.pop(session_id, None)

    async def get(self, session_id: str) -> list[dict[str, Any]]:
        self._purge_if_expired(session_id)
        session = self._sessions.get(session_id)
        if not session:
            return []

        messages, _ = session
        self._sessions[session_id] = (messages, self._expires_at())
        return list(messages)

    async def append(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        current = await self.get(session_id)
        current.extend(messages)
        self._sessions[session_id] = (current, self._expires_at())

    async def exists(self, session_id: str) -> bool:
        self._purge_if_expired(session_id)
        return session_id in self._sessions

    async def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    async def close(self) -> None:
        return None


class RedisSessionStore:
    """Redis-backed session store using one list key per chat session."""

    def __init__(self, broker_url: str, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self.redis_url = _with_database(broker_url, CHATBOT_SESSIONS_DB)
        self.client = Redis.from_url(self.redis_url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"{SESSION_KEY_PREFIX}{session_id}"

    async def get(self, session_id: str) -> list[dict[str, Any]]:
        key = self._key(session_id)
        values = await self.client.lrange(key, 0, -1)
        if not values:
            return []

        await self.client.expire(key, self.ttl_seconds)
        messages: list[dict[str, Any]] = []
        for value in values:
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                logger.warning("Skipping invalid session message for %s", session_id)
                continue
            if isinstance(decoded, dict):
                messages.append(decoded)
        return messages

    async def append(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        if not messages:
            return

        key = self._key(session_id)
        encoded = [json.dumps(message, default=str) for message in messages]
        async with self.client.pipeline(transaction=True) as pipe:
            pipe.rpush(key, *encoded)
            pipe.expire(key, self.ttl_seconds)
            await pipe.execute()

    async def exists(self, session_id: str) -> bool:
        return bool(await self.client.exists(self._key(session_id)))

    async def delete(self, session_id: str) -> bool:
        return bool(await self.client.delete(self._key(session_id)))

    async def close(self) -> None:
        await self.client.aclose()


def create_session_store(ttl_seconds: int) -> SessionStore:
    broker_url = os.getenv("BROKER_URL")
    if not broker_url:
        logger.info("BROKER_URL not set; using in-memory chatbot session store")
        return InMemorySessionStore(ttl_seconds=ttl_seconds)

    logger.info("Using Redis chatbot session store on DB %s", CHATBOT_SESSIONS_DB)
    return RedisSessionStore(broker_url=broker_url, ttl_seconds=ttl_seconds)


def _with_database(redis_url: str, database: int) -> str:
    parts = urlsplit(redis_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))
