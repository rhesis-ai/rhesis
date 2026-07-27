"""Hatch build hook: vendor the shared Architect skill references.

`python -m build` builds the sdist first, then builds the wheel from that
sdist inside an isolated temp dir where the monorepo's `../skills` directory
no longer exists — a static `force-include` pointing there raises
`FileNotFoundError` in that second stage. This hook only force-includes the
directory when it is actually present, which covers all three build paths:

- `uv build --wheel` / `hatch build --target wheel` from a checkout:
  `../skills` exists, so it's force-included directly into the wheel.
- `hatch build --target sdist` from a checkout: `../skills` exists, so it's
  vendored into the sdist at the same destination the wheel expects.
- Building the wheel from that already-vendored sdist: `../skills` no longer
  exists, so the hook is a no-op, and the files are already present in the
  extracted sdist tree, picked up by the normal package file selection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_SKILL_REFS_SOURCE = ("..", "skills", "rhesis", "references")
_SKILL_REFS_DEST = "src/rhesis/sdk/agents/architect/prompt_templates/skill_refs"


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        source = Path(self.root, *_SKILL_REFS_SOURCE)
        if source.is_dir():
            build_data.setdefault("force_include", {})[str(source)] = _SKILL_REFS_DEST
