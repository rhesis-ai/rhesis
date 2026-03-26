"""Redis database allocation registry.

All Redis database numbers used by the application are defined here.
The base Redis URL comes from BROKER_URL (default: redis://localhost:6379/0).
Each subsystem overrides the /db path suffix as needed.

This module prevents accidental DB number collisions and documents each
database's purpose in a single location.
"""


class RedisDatabase:
    CELERY_BROKER = 0
    CELERY_RESULT_BACKEND = 1
    GARAK_PROBE_CACHE = 2
    CONVERSATION_LINKING = 3
    TRACE_METRICS_DEBOUNCE = 3  # shares DB with conversation linking (different key prefixes)
