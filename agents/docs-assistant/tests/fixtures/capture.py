"""Refresh the docs fixtures from the live site.

    uv run python tests/fixtures/capture.py

Keeps a handful of pages so the tests stay small and offline. Re-run it when the docs change
shape (frontmatter, headings) and review the diff.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx

BASE = "https://docs.rhesis.ai"
HERE = Path(__file__).parent
PAGES = [
    "docs/metrics/metric-scope",
    "docs/endpoints/response-mapping",
    "docs/endpoints/sdk-endpoints",
    "docs/api-tokens",
    "sdk/installation",
    "sdk/metrics",
    "self-hosting/docker-compose",
    "changelog",
]
# Index-only glossary terms (listed in llms.txt, missing from llms-full.txt).
INDEX_ONLY = ["glossary/hallucination", "glossary/prompt-injection"]
CHANGELOG_VERSIONS = 3


def _blocks(full: str) -> dict[str, str]:
    starts = [m.start() for m in re.finditer(r"^---\nurl: ", full, re.MULTILINE)]
    blocks = {}
    for i, start in enumerate(starts):
        block = full[start : starts[i + 1] if i + 1 < len(starts) else len(full)]
        url = re.match(r"---\nurl: (\S+)", block).group(1)
        blocks[url.removeprefix(f"{BASE}/")] = block
    return blocks


def _trim_changelog(block: str) -> str:
    # Keep [Unreleased] plus the latest few versions.
    heads = [m.start() for m in re.finditer(r"^## \[", block, re.MULTILINE)]
    return block[: heads[CHANGELOG_VERSIONS + 1]] if len(heads) > CHANGELOG_VERSIONS + 1 else block


def main() -> None:
    full = httpx.get(f"{BASE}/llms-full.txt", timeout=30).text
    index = httpx.get(f"{BASE}/llms.txt", timeout=30).text
    blocks = _blocks(full)
    kept = [_trim_changelog(blocks[p]) if p == "changelog" else blocks[p] for p in PAGES]
    header = full[: full.index("---\nurl: ")]
    (HERE / "llms-full.txt").write_text(header + "".join(kept).rstrip("\n") + "\n")

    wanted = {f"{BASE}/{p}.md" for p in PAGES + INDEX_ONLY}
    lines, seen = [], set()
    for line in index.splitlines():
        match = re.match(r"- \[[^\]]+\]\(([^)]+)\)", line)
        if match is None:
            if line.startswith("#") or line.startswith(">") or not line.strip():
                lines.append(line)
            continue
        if match.group(1) in wanted and match.group(1) not in seen:
            seen.add(match.group(1))
            lines.append(line)
    (HERE / "llms.txt").write_text(re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n")
    print(f"kept {len(kept)} pages and {len(seen)} index entries")


if __name__ == "__main__":
    main()
