"""OWASP Top 10 report category service.

Wraps the SDK's ``fetch_owasp_sections`` with two caches so the PDF download +
pdfminer parse happens at most once per framework (and again whenever the
framework's report URL changes — see :func:`_versioned_cache_key`):

- A permanent content cache (parsed sections as ``owasp/{cache_key}.json`` in
  the object store, no TTL) shared by the categories endpoint and the
  generation task.
- A Redis id/name-only cache in front of it (7-day TTL) so the frontend's
  category picker avoids a storage round-trip.
"""

import hashlib
import json
import logging
from typing import Dict, List, Optional

from rhesis.backend.app.services.cache import RedisBackedCache
from rhesis.backend.app.services.redis_constants import RedisDatabase
from rhesis.backend.app.services.storage_service import StorageService
from rhesis.sdk.services.owasp_extractor import (
    DEFAULT_OWASP_AGENTIC_PDF_URL,
    DEFAULT_OWASP_LLM_PDF_URL,
    fetch_owasp_sections,
)

logger = logging.getLogger(__name__)

# Framework id -> report URL / behavior label stamped on generated tests.
# `behavior` is read both here (routers/owasp.py) and by
# tasks/test_set.py:generate_and_save_owasp_test_set — keep the single key so
# the two call sites can't drift apart.
OWASP_FRAMEWORKS: Dict[str, Dict[str, str]] = {
    "llm": {
        "report_url": DEFAULT_OWASP_LLM_PDF_URL,
        "behavior": "OWASP LLM Top 10",
    },
    "agentic": {
        "report_url": DEFAULT_OWASP_AGENTIC_PDF_URL,
        "behavior": "OWASP Agentic Top 10",
    },
}

_CACHE_TTL = 86400 * 7  # 7 days - Redis metadata cache only; content cache never expires

# Bump on any future incompatible change to the cached payload shape. Old
# entries are simply never read again under the new prefix and age out on
# their own (TTL for Redis; orphaned-but-harmless for the object store) --
# no runtime shape-sniffing needed to tell old and new entries apart.
_CACHE_SCHEMA_VERSION = "v2"


def _versioned_cache_key(framework: str) -> str:
    """Composite cache key: schema version + framework + report-URL hash.

    Used for both the Redis metadata cache and the object-store content
    cache, so a framework's report URL changing (new PDF revision, or a
    corrected/moved URL) naturally invalidates both: the hash changes, a
    fresh parse happens, and the old entry is simply never read again
    instead of being served indefinitely.
    """
    report_url = OWASP_FRAMEWORKS[framework]["report_url"]
    url_hash = hashlib.sha256(report_url.encode("utf-8")).hexdigest()[:12]
    return f"{_CACHE_SCHEMA_VERSION}-{framework}-{url_hash}"


class OwaspSectionCache(RedisBackedCache):
    """Redis-backed cache with in-memory fallback for OWASP report section metadata."""

    def __init__(self) -> None:
        super().__init__(
            redis_db=RedisDatabase.OWASP_SECTIONS_CACHE,
            cache_name="owasp-sections",
            ttl=_CACHE_TTL,
        )

    def get_sections(self, framework: str) -> Optional[List[dict]]:
        raw = self._get(f"owasp:sections:{_versioned_cache_key(framework)}")
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None

    def set_sections(self, framework: str, sections: List[dict]) -> None:
        self._set(f"owasp:sections:{_versioned_cache_key(framework)}", json.dumps(sections))


_cache = OwaspSectionCache()

_storage_service: Optional[StorageService] = None


def _get_storage() -> StorageService:
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service


def load_owasp_content_cache(framework: str) -> Optional[List[dict]]:
    """``cache_loader`` for ``fetch_owasp_sections``: read cached sections or None."""
    storage = _get_storage()
    cache_key = _versioned_cache_key(framework)
    raw = storage.get_object_bytes(storage.get_owasp_content_path(cache_key))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError) as e:
        logger.warning(f"Corrupt OWASP content cache for {framework!r}, ignoring: {e}")
        return None


def save_owasp_content_cache(framework: str, sections: List[dict]) -> None:
    """``cache_writer`` for ``fetch_owasp_sections``: persist parsed sections (no TTL).

    Storage failures are logged and swallowed so a misconfigured local path
    (e.g. Docker's ``file:///app/storage`` on a Mac host) does not discard a
    successful parse — Redis still gets the id/name metadata for the picker.
    Caught broadly since ``StorageService`` writes go through ``fsspec``,
    and cloud backends (gcsfs, s3fs, ...) can raise a variety of native
    exception types on write failure.
    """
    storage = _get_storage()
    cache_key = _versioned_cache_key(framework)
    payload = json.dumps(sections).encode("utf-8")
    try:
        storage.put_object_bytes(
            payload, storage.get_owasp_content_path(cache_key), "application/json"
        )
    except Exception as e:
        logger.warning(
            "Failed to persist OWASP content cache for %r (%s); continuing without it",
            framework,
            e,
        )


def _short_description(content: str, max_len: int = 180) -> str:
    """Extract a one-line blurb from a section's Description/Overview subsection."""
    if not content:
        return ""

    lines = content.split("\n")
    collected: list[str] = []
    capture = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if capture:
                break
            heading = stripped[3:].strip().lower()
            capture = heading in {"description", "overview"}
            continue
        if stripped.startswith("# "):
            if capture:
                break
            continue
        if capture and stripped:
            collected.append(stripped)
            if len(" ".join(collected)) >= max_len:
                break

    if not collected:
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                if collected:
                    break
                continue
            collected.append(stripped)
            if len(" ".join(collected)) >= max_len:
                break

    text = " ".join(collected).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text


def list_category_summaries(framework: str) -> List[dict]:
    """Return ``[{id, name, description}, ...]`` for the category picker."""
    if framework not in OWASP_FRAMEWORKS:
        valid = sorted(OWASP_FRAMEWORKS)
        raise ValueError(f"Unknown OWASP framework {framework!r}. Valid: {valid}")

    _cache.initialize()
    cached = _cache.get_sections(framework)
    if cached is not None:
        return cached

    report_url = OWASP_FRAMEWORKS[framework]["report_url"]
    sections = fetch_owasp_sections(
        report_url,
        cache_key=framework,
        cache_loader=load_owasp_content_cache,
        cache_writer=save_owasp_content_cache,
    )
    summaries = [
        {
            "id": s.id,
            "name": s.name,
            "description": _short_description(s.content),
        }
        for s in sections
    ]
    _cache.set_sections(framework, summaries)
    return summaries
