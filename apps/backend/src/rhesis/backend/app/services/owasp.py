"""OWASP Top 10 report category service.

Wraps the SDK's ``fetch_owasp_sections`` (downloads and parses the official
OWASP Top 10 PDF) with a Redis-backed cache so the frontend's category picker
doesn't re-download/re-parse the report on every drawer open.
"""

import json
import logging
from typing import Dict, List, Optional

from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase
from rhesis.sdk.services.owasp_extractor import (
    DEFAULT_OWASP_AGENTIC_PDF_URL,
    DEFAULT_OWASP_LLM_PDF_URL,
    ReportSection,
    fetch_owasp_sections,
)

logger = logging.getLogger(__name__)

# Framework id -> report URL / behavior label stamped on generated tests.
OWASP_FRAMEWORKS: Dict[str, Dict[str, str]] = {
    "llm": {
        "report_url": DEFAULT_OWASP_LLM_PDF_URL,
        "behavior": "OWASP LLM Top 10",
        "label": "OWASP LLM Top 10",
    },
    "agentic": {
        "report_url": DEFAULT_OWASP_AGENTIC_PDF_URL,
        "behavior": "OWASP Agentic Top 10",
        "label": "OWASP Agentic Top 10",
    },
}

_CACHE_TTL = 86400 * 7  # 7 days - the published report rarely changes


class OwaspSectionCache(RedisBackedCache):
    """Redis-backed cache with in-memory fallback for OWASP report section metadata."""

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.OWASP_SECTIONS_CACHE,
            cache_name="owasp-sections",
            ttl=_CACHE_TTL,
        )

    def get_sections(self, framework: str) -> Optional[List[dict]]:
        raw = self._get(f"owasp:sections:{framework}")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def set_sections(self, framework: str, sections: List[dict]) -> None:
        self._set(f"owasp:sections:{framework}", json.dumps(sections))


_cache = OwaspSectionCache()


def list_categories(framework: str) -> List[ReportSection]:
    """Return the report sections (id, name) for *framework*, using the cache when warm."""
    if framework not in OWASP_FRAMEWORKS:
        valid = sorted(OWASP_FRAMEWORKS)
        raise ValueError(f"Unknown OWASP framework {framework!r}. Valid: {valid}")

    _cache.initialize()
    cached = _cache.get_sections(framework)
    if cached is not None:
        return [ReportSection(id=s["id"], name=s["name"], content="") for s in cached]

    report_url = OWASP_FRAMEWORKS[framework]["report_url"]
    sections = fetch_owasp_sections(report_url)
    _cache.set_sections(framework, [{"id": s.id, "name": s.name} for s in sections])
    return sections
