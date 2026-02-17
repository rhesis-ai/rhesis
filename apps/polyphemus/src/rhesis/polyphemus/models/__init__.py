"""
Polyphemus models package.

Polyphemus is an API-only service: it authenticates users, applies rate limits,
and proxies /generate requests to Vertex AI. It does not load or run models
locally; all inference is done on Vertex AI endpoints.
"""

__all__: list[str] = []
