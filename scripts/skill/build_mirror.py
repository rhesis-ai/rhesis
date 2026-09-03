#!/usr/bin/env python3
"""
Build the contents of the rhesis-ai/skills mirror from skills/rhesis/ in this monorepo.

The mirror is a read-only distribution artifact: the skill body is copied verbatim and
every manifest at its root is generated here. No manifest carries a `version` field —
Claude Code then falls back to the source commit SHA, so users receive an update on every
sync without anyone bumping anything.

Usage (from repo root):
    python scripts/skill/build_mirror.py --out build/skills-mirror
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

SOURCE_REPO = "rhesis-ai/rhesis"
MIRROR_REPO = "rhesis-ai/skills"

# Contributor instructions for this monorepo — not part of what users install.
NOT_PUBLISHED = ("AGENTS.md", "CLAUDE.md")

AUTHOR = {"name": "Rhesis AI", "url": "https://rhesis.ai"}
HOMEPAGE = "https://rhesis.ai"
LICENSE = "MIT"
KEYWORDS = ["ai-testing", "mcp", "evaluation", "llm-testing", "rhesis"]
DESCRIPTION = (
    "Design, run, and analyze AI test suites on Rhesis — explore endpoints, build test "
    "foundations from requirements, and drive the full workflow via MCP."
)

BANNER = f"""> [!NOTE]
> **This is a read-only mirror.** The skill is developed in
> [`{SOURCE_REPO}`](https://github.com/{SOURCE_REPO}/tree/main/skills/rhesis) and synced here
> automatically. Pull requests opened here cannot be merged — please open them against the
> source repo instead.

"""

SOURCE_URL = f"https://github.com/{SOURCE_REPO}"

CONTRIBUTING = f"""# Contributing

This repository is a **read-only mirror**. Its contents are generated from
[`{SOURCE_REPO}`]({SOURCE_URL}) and refreshed on every change to `skills/rhesis/` there.

Direct pushes to `main` are blocked — only the sync bot can write here, and any content that
did land out of band would be reverted by the next sync.

## Where to make changes

All paths below are in [`{SOURCE_REPO}`]({SOURCE_URL}).

| Change | Where |
|---|---|
| Skill instructions, references, MCP guidance | `skills/rhesis/` |
| Plugin manifests, README banner, this file | `scripts/skill/build_mirror.py` |
| Bug reports, feature requests | [Open an issue]({SOURCE_URL}/issues) |

## Local development

Clone the source repo and point your agent at `skills/rhesis/` directly — no need to wait
for a sync.
"""


def build_claude_plugin() -> dict:
    """Claude Code plugin manifest. No `version`: see module docstring."""
    return {
        "name": "rhesis",
        "description": DESCRIPTION,
        "author": AUTHOR,
        "homepage": HOMEPAGE,
        "repository": f"https://github.com/{MIRROR_REPO}",
        "license": LICENSE,
        "keywords": KEYWORDS,
        # skills/ at the plugin root is scanned by default, so no `skills` field is needed.
        # .mcp.json is not at the plugin root, so that one must be declared.
        "mcpServers": "./skills/rhesis/.mcp.json",
        # Prompts for the API key at install time and stores it in the OS keychain, so
        # users no longer have to place it themselves. `sensitive` keeps it out of
        # settings.json; `description` is required by the manifest schema.
        #
        # Deliberately not `required`: the key is also readable from RHESIS_API_KEY, and
        # marking it required would block anyone already set up that way when the plugin
        # updates. `.mcp.json` falls back to the environment variable.
        "userConfig": {
            "api_key": {
                "type": "string",
                "title": "Rhesis API key",
                "description": (
                    "Generate one at https://app.rhesis.ai/tokens. Leave blank to use the "
                    "RHESIS_API_KEY environment variable instead."
                ),
                "sensitive": True,
            }
        },
    }


def build_marketplace() -> dict:
    return {
        "name": "rhesis-ai",
        "owner": AUTHOR,
        "metadata": {"description": "Rhesis AI plugin marketplace — AI testing tools and skills"},
        "plugins": [
            {
                "name": "rhesis",
                "source": "./",
                "description": "Design, run, and analyze AI test suites on the Rhesis platform",
                "category": "testing",
                "tags": ["ai-testing", "mcp", "evaluation", "llm-testing"],
            }
        ],
    }


def build_cursor_plugin() -> dict:
    return {
        "name": "rhesis",
        "displayName": "Rhesis",
        "description": DESCRIPTION,
        "author": AUTHOR,
        "homepage": HOMEPAGE,
        "repository": f"https://github.com/{MIRROR_REPO}",
        "license": LICENSE,
        "keywords": KEYWORDS,
        "category": "developer-tools",
        "skills": "./skills/",
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", default=Path("skills/rhesis"), type=Path)
    parser.add_argument("--out", required=True, type=Path, help="Directory to build into")
    args = parser.parse_args()

    skill_dir: Path = args.skill_dir
    out: Path = args.out

    if not skill_dir.is_dir():
        print(f"error: {skill_dir} is not a directory", file=sys.stderr)
        return 2

    # Rebuild from scratch so deletions in the source propagate to the mirror.
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    shutil.copytree(
        skill_dir,
        out / "skills" / skill_dir.name,
        ignore=shutil.ignore_patterns(*NOT_PUBLISHED),
    )

    write_json(out / ".claude-plugin" / "plugin.json", build_claude_plugin())
    write_json(out / ".claude-plugin" / "marketplace.json", build_marketplace())
    write_json(out / ".cursor-plugin" / "plugin.json", build_cursor_plugin())

    (out / "README.md").write_text(BANNER + (skill_dir / "README.md").read_text())
    (out / "CONTRIBUTING.md").write_text(CONTRIBUTING)
    shutil.copyfile(skill_dir / "LICENSE", out / "LICENSE")

    print(f"Built mirror contents in {out}")
    for path in sorted(out.rglob("*")):
        if path.is_file():
            print(f"  {path.relative_to(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
