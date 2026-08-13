"""Redis database allocation registry.

All Redis database numbers used by the application are defined here.
The base Redis URL comes from RedisSettings.
Each subsystem overrides the /db path suffix as needed.

When BROKER_READ_URL is set, cache read operations (_get, _mget) are
routed to a read replica while writes stay on BROKER_URL. If unset,
all operations use BROKER_URL.

This module prevents accidental DB number collisions and documents each
database's purpose in a single location.
"""


class RedisDatabase:
    CELERY_BROKER = 0
    CELERY_RESULT_BACKEND = 1
    GARAK_PROBE_CACHE = 2
    CONVERSATION_LINKING = 3
    TRACE_METRICS_DEBOUNCE = 3  # shares DB with conversation linking (different key prefixes)
    CHATBOT_SESSIONS = 4
    PERMISSION_CACHE = 5  # authorization PDP decision cache (SP5)
    OWASP_SECTIONS_CACHE = 6
