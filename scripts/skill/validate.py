#!/usr/bin/env python3
"""
Validate the published Rhesis agent skill before it is mirrored to rhesis-ai/skills.

The skill is authored in this monorepo under skills/rhesis/ and synced to a standalone
public repo. Anything that only resolves because of the monorepo around it will 404 for
users of the mirror, so this catches that before it ships.

Checks:
  1. SKILL.md has frontmatter with name + description, and name matches the directory.
  2. Every reference named in references/workflow-index.md exists.
  3. Every relative markdown link resolves to a file inside the skill directory.

App routes (``/test-runs/<id>``) and hosted glossary paths (``glossary/*.md``) are not
files and are skipped.

Usage (from repo root):
    python scripts/skill/validate.py
    python scripts/skill/validate.py --skill-dir skills/rhesis
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Backtick-quoted markdown filenames, e.g. `phases/creation.md`.
BACKTICK_MD = re.compile(r"`([^`\s]+\.md)`")
# Inline markdown links, e.g. [label](target).
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Frontmatter block delimited by --- on its own line.
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

# Hosted on docs.rhesis.ai, not shipped in the skill.
EXTERNAL_MD_PREFIXES = ("glossary/",)

# Contributor instructions, excluded from the mirror, so monorepo paths are legal in them.
NOT_PUBLISHED = {"AGENTS.md", "CLAUDE.md"}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_frontmatter(skill_dir: Path, errors: list[str]) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        fail(errors, f"{skill_md}: missing")
        return

    match = FRONTMATTER.match(skill_md.read_text())
    if not match:
        fail(errors, f"{skill_md}: no YAML frontmatter block")
        return

    block = match.group(1)
    name = re.search(r"^name:\s*(\S+)\s*$", block, re.MULTILINE)
    if not name:
        fail(errors, f"{skill_md}: frontmatter has no `name`")
    elif name.group(1) != skill_dir.name:
        fail(
            errors,
            f"{skill_md}: frontmatter name '{name.group(1)}' != directory '{skill_dir.name}'",
        )

    if not re.search(r"^description:", block, re.MULTILINE):
        fail(errors, f"{skill_md}: frontmatter has no `description`")


def resolve_md_token(token: str, source: Path, skill_dir: Path) -> Path | None:
    """Resolve a backticked filename against the places the skill refers to things from."""
    for candidate in (source.parent / token, skill_dir / "references" / token, skill_dir / token):
        if candidate.is_file():
            return candidate
    return None


def check_workflow_index(skill_dir: Path, errors: list[str]) -> None:
    index = skill_dir / "references" / "workflow-index.md"
    if not index.is_file():
        fail(errors, f"{index}: missing — it is the skill's router")
        return

    for token in sorted(set(BACKTICK_MD.findall(index.read_text()))):
        if token.startswith(EXTERNAL_MD_PREFIXES):
            continue
        if resolve_md_token(token, index, skill_dir) is None:
            fail(errors, f"{index}: references `{token}`, which does not exist")


def check_links(skill_dir: Path, errors: list[str]) -> None:
    for source in sorted(skill_dir.rglob("*.md")):
        if source.name in NOT_PUBLISHED:
            continue
        for target in MD_LINK.findall(source.read_text()):
            target = target.split()[0].strip("<>")
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            # Absolute paths that are not markdown are Rhesis app routes, not files.
            if target.startswith("/") and not target.endswith(".md"):
                continue

            path = target.split("#", 1)[0]
            if not path:
                continue

            resolved = (source.parent / path).resolve()
            try:
                resolved.relative_to(skill_dir.resolve())
            except ValueError:
                fail(errors, f"{source}: link '{target}' escapes the skill directory")
                continue
            if not resolved.exists():
                fail(errors, f"{source}: link '{target}' does not resolve")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-dir", default="skills/rhesis", type=Path)
    args = parser.parse_args()

    skill_dir: Path = args.skill_dir
    if not skill_dir.is_dir():
        print(f"error: {skill_dir} is not a directory", file=sys.stderr)
        return 2

    errors: list[str] = []
    check_frontmatter(skill_dir, errors)
    check_workflow_index(skill_dir, errors)
    check_links(skill_dir, errors)

    if errors:
        print(f"Skill validation failed ({len(errors)} problem(s)):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"Skill validation passed: {skill_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
