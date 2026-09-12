"""Compare two benchmark result files and print a markdown table.

uv run python ../../tests/benchmarks/compare.py results/baseline.json results/after.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _flatten(prefix: str, node: Any, out: dict[str, float]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _flatten(f"{prefix}.{key}" if prefix else key, value, out)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out[prefix] = float(node)


def _fmt(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.2f}"


def main(before_path: str, after_path: str) -> None:
    before = json.loads(Path(before_path).read_text())
    after = json.loads(Path(after_path).read_text())
    flat_before: dict[str, float] = {}
    flat_after: dict[str, float] = {}
    _flatten("", before["scenarios"], flat_before)
    _flatten("", after["scenarios"], flat_after)

    print(f"| metric | {before['label']} | {after['label']} | change |")
    print("| --- | ---: | ---: | ---: |")
    for key in sorted(set(flat_before) | set(flat_after)):
        if key.endswith(".samples") or key.endswith(".seed_tests"):
            continue
        b = flat_before.get(key)
        a = flat_after.get(key)
        if b is None or a is None:
            left = _fmt(b) if b is not None else "-"
            right = _fmt(a) if a is not None else "-"
            print(f"| {key} | {left} | {right} | |")
            continue
        change = "" if b == 0 else f"{(a - b) / b * 100:+.0f}%"
        print(f"| {key} | {_fmt(b)} | {_fmt(a)} | {change} |")

    for data in (before, after):
        plan = data["scenarios"].get("list_queries", {}).get("prompt_list_explain")
        if plan:
            print(f"\n<details><summary>prompt list plan ({data['label']})</summary>\n")
            print(f"```\n{plan}\n```\n</details>")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
