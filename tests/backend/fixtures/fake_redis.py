"""An in-memory stand-in for the async Redis client behind ``redis_manager``.

The real client is bound to the event loop that opened it, and TestClient and
pytest-asyncio each run their own loops, so tests that need Redis state to be
read back swap this in instead.
"""

from contextlib import contextmanager
from unittest.mock import patch

_REDIS_MGR = "rhesis.backend.app.services.connector.redis_client.redis_manager"


class FakeRedis:
    """The handful of commands the auth stores use. TTLs are recorded, not enforced."""

    def __init__(self):
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return None
        self.data[key] = str(value)
        if ex is not None:
            self.ttls[key] = ex
        return True

    async def getdel(self, key):
        return self.data.pop(key, None)

    async def delete(self, key):
        return 1 if self.data.pop(key, None) is not None else 0


class _FakeManager:
    def __init__(self, client, available):
        self.client = client
        self.is_available = available

    async def initialize(self):
        return None


@contextmanager
def fake_redis_manager(client=None, *, available=True):
    """Patch ``redis_manager`` with ``client`` (a new FakeRedis by default)."""
    client = client if client is not None else FakeRedis()
    with patch(_REDIS_MGR, _FakeManager(client, available)):
        yield client
