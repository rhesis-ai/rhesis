"""
Catalog of garak tag descriptions loaded from garak's own tags.misp.tsv.

Provides a single-source-of-truth for tag→description and tag→topic mappings
without hard-coding them in the application. The TSV ships with every garak
release and is kept in sync with the taxonomy used by probes.

Tags that are absent from the TSV (e.g. ``payload:*`` tags) are resolved
from a small static fallback table.
"""

import csv
import logging
import pathlib
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Static fallback for tags not present in tags.misp.tsv
_PAYLOAD_TOPIC_FALLBACK: Dict[str, str] = {
    "payload:jailbreak": "Jailbreak",
    "payload:unwanted": "Unwanted Content",
    "payload:generic": "Generic Attacks",
}


class GarakTagCatalog:
    """
    Lazy-loaded catalog backed by ``garak/data/tags.misp.tsv``.

    The TSV is tab-separated with three columns (no header row)::

        key<TAB>title<TAB>description

    For example::

        owasp:llm01  LLM01: Prompt Injection  Crafty inputs can manipulate ...
    """

    def __init__(self) -> None:
        self._entries: Optional[Dict[str, Dict[str, str]]] = None

    def _ensure_loaded(self) -> Dict[str, Dict[str, str]]:
        if self._entries is not None:
            return self._entries

        self._entries = {}
        tsv_path = self._find_tsv()
        if tsv_path is None:
            logger.warning("garak tags.misp.tsv not found; tag descriptions will be unavailable")
            return self._entries

        try:
            with open(tsv_path, newline="") as fh:
                reader = csv.reader(fh, delimiter="\t")
                for row in reader:
                    if len(row) < 2:
                        continue
                    key = row[0].strip()
                    title = row[1].strip() if len(row) > 1 else ""
                    description = row[2].strip() if len(row) > 2 else ""
                    self._entries[key] = {
                        "title": title,
                        "description": description,
                    }
            logger.debug(
                "Loaded %d tag entries from %s",
                len(self._entries),
                tsv_path,
            )
        except Exception:
            logger.exception("Failed to parse garak tags.misp.tsv")
            self._entries = {}

        return self._entries

    def get_description(self, tag: str) -> Optional[str]:
        """
        Return a human-readable description for *tag*.

        Combines the TSV title and description into a single string, e.g.::

            "LLM01: Prompt Injection — Crafty inputs can manipulate ..."

        Returns ``None`` for unknown tags.
        """
        entries = self._ensure_loaded()
        entry = entries.get(tag)
        if entry:
            title = entry["title"]
            desc = entry["description"]
            if title and desc:
                return f"{title} — {desc}"
            return title or desc or None
        return None

    def get_topic(self, tag: str) -> Optional[str]:
        """
        Return a short topic label for *tag*.

        For TSV entries the title is returned (e.g. ``"LLM01: Prompt Injection"``).
        For ``payload:*`` tags a static fallback is used.  Returns ``None`` for
        unknown tags.
        """
        entries = self._ensure_loaded()
        entry = entries.get(tag)
        if entry:
            return entry["title"] or None
        return _PAYLOAD_TOPIC_FALLBACK.get(tag)

    @property
    def size(self) -> int:
        """Number of entries loaded from the TSV."""
        return len(self._ensure_loaded())

    @staticmethod
    def _find_tsv() -> Optional[pathlib.Path]:
        """Locate ``garak/data/tags.misp.tsv`` relative to the garak package."""
        try:
            import garak

            tsv = pathlib.Path(garak.__file__).parent / "data" / "tags.misp.tsv"
            return tsv if tsv.exists() else None
        except ImportError:
            return None


# Module-level singleton — reused across the application
_catalog: Optional[GarakTagCatalog] = None


def get_tag_catalog() -> GarakTagCatalog:
    """Return the shared :class:`GarakTagCatalog` singleton."""
    global _catalog
    if _catalog is None:
        _catalog = GarakTagCatalog()
    return _catalog
