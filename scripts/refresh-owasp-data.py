#!/usr/bin/env python3
"""Re-extract OWASP Top 10 PDFs into the bundled JSON files shipped with the SDK.

Run from the repo root:
    uv run --project sdk scripts/refresh-owasp-data.py

Exits 0 when files were updated (or already up to date), non-zero on failure.
The GitHub Actions workflow uses git diff to detect actual changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from rhesis.sdk.services.owasp_extractor import (
    DEFAULT_OWASP_AGENTIC_PDF_URL,
    DEFAULT_OWASP_LLM_PDF_URL,
    _extract_pdf,
    _fetch_pdf_bytes,
    _parse_sections,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "sdk" / "src" / "rhesis" / "sdk" / "services" / "data" / "owasp"

# The LLM PDF URL redirects to a 404 on owasp.org since their site restructure.
# Use the GitHub raw URL which hosts the same file.
_FETCH_URLS: dict[str, str] = {
    "llm-top-10-2025": (
        "https://raw.githubusercontent.com/OWASP/"
        "www-project-top-10-for-large-language-model-applications/"
        "main/assets/PDF/OWASP-Top-10-for-LLMs-v2025.pdf"
    ),
    "agentic-top-10-2025": DEFAULT_OWASP_AGENTIC_PDF_URL,
}

_CANONICAL_URLS: dict[str, str] = {
    "llm-top-10-2025": DEFAULT_OWASP_LLM_PDF_URL,
    "agentic-top-10-2025": DEFAULT_OWASP_AGENTIC_PDF_URL,
}


def extract_report(name: str) -> None:
    fetch_url = _FETCH_URLS[name]
    canonical_url = _CANONICAL_URLS[name]

    print(f"Downloading {name} from {fetch_url} ...")
    pdf_bytes = _fetch_pdf_bytes(fetch_url)
    print(f"  {len(pdf_bytes):,} bytes, extracting sections ...")

    sections = _parse_sections(_extract_pdf(pdf_bytes))
    if not sections:
        raise ValueError(f"No sections extracted from {name}")

    data = {
        "source_url": canonical_url,
        "report": name,
        "sections": [
            {"id": s.id, "name": s.name, "content": s.content}
            for s in sections
        ],
    }

    out_path = OUT_DIR / f"{name}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  -> {out_path.relative_to(REPO_ROOT)} ({len(sections)} sections)")


def main() -> None:
    failed = []
    for name in _FETCH_URLS:
        try:
            extract_report(name)
        except Exception as exc:
            print(f"  FAILED: {exc}", file=sys.stderr)
            failed.append(name)

    if failed:
        print(f"\nFailed reports: {failed}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
