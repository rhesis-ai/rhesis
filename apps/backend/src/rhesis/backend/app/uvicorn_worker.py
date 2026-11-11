"""Gunicorn worker class that applies the backend's WebSocket limits.

uvicorn otherwise accepts 16 MiB frames and queues 32 messages per connection before
the app sees any of them, so a client could pin about 512 MB per socket.
"""

from uvicorn.workers import UvicornWorker

from rhesis.backend.app.constants import WS_MAX_MESSAGE_SIZE, WS_MAX_QUEUE


class RhesisUvicornWorker(UvicornWorker):
    CONFIG_KWARGS = {
        **UvicornWorker.CONFIG_KWARGS,
        "ws_max_size": WS_MAX_MESSAGE_SIZE,
        "ws_max_queue": WS_MAX_QUEUE,
    }
