#!/usr/bin/env python3
"""
Run pip-audit for every Python project (pyproject.toml) in the repository in parallel,
then write a single Markdown report at the repository root.

Looks for pyproject.toml (and pyproject.yaml if present). Repositories typically use
toml; there is no separate YAML standard for the same file.

Usage (from repo root):
    uv run python scripts/run_pip_audit_all.py
    uv run python scripts/run_pip_audit_all.py -j 8

By default pip-audit is invoked as ``uv run --with pip-audit pip-audit`` so audits work
without adding pip-audit to every pyproject. Use ``--bare`` for plain ``uv run pip-audit``.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPORT_FILENAME = "pip-audit-report.md"

# Noisy pip/OSV client log lines (CacheControl); not useful in the report.
_CACHECONTROL_DESER_WARN = re.compile(
    r"cachecontrol\.controller.*Cache entry deserialization failed",
    re.IGNORECASE,
)
# PyPI metadata gaps (e.g. torch wheels) vs exclude-newer cutoff — noisy, not actionable in report.
_MISSING_UPLOAD_DATE_WARN = re.compile(
    r"is missing an upload date,\s*but user provided:",
    re.IGNORECASE,
)


def filter_audit_noise(text: str) -> str:
    """Drop known-noisy warnings from subprocess output (report only)."""
    lines: list[str] = []
    for ln in text.splitlines():
        if _CACHECONTROL_DESER_WARN.search(ln):
            continue
        if _MISSING_UPLOAD_DATE_WARN.search(ln):
            continue
        lines.append(ln)
    return "\n".join(lines)


# Directories to skip when walking the tree (name match on path parts).
SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "dist",
        "build",
        ".next",
        "out",
    }
)


@dataclass
class AuditResult:
    package_name: str
    project_dir: Path
    pyproject: Path
    returncode: int
    stdout: str
    stderr: str


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def package_label(pyproject: Path) -> str:
    if pyproject.suffix == ".toml":
        return parse_project_name(pyproject)
    return pyproject.parent.name


def parse_project_name(pyproject_path: Path) -> str:
    """Read [project].name from pyproject.toml without extra dependencies."""
    text = pyproject_path.read_text(encoding="utf-8")
    in_project = False
    name_re = re.compile(r'^name\s*=\s*["\']([^"\']+)["\']')
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line == "[project]":
            in_project = True
            continue
        if line.startswith("[") and line.endswith("]"):
            if in_project:
                break
            in_project = False
            continue
        if in_project:
            m = name_re.match(line)
            if m:
                return m.group(1)
    return pyproject_path.parent.name


def discover_pyprojects(root: Path) -> list[Path]:
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        p = Path(dirpath)
        for fname in ("pyproject.toml", "pyproject.yaml"):
            if fname in filenames:
                found.append(p / fname)
                break
    return sorted(set(found))


def run_one(pyproject: Path, uv_bin: str, bare_uv_run: bool) -> AuditResult:
    project_dir = pyproject.parent
    name = package_label(pyproject)
    cmd = (
        [uv_bin, "run", "pip-audit"]
        if bare_uv_run
        else [uv_bin, "run", "--with", "pip-audit", "pip-audit"]
    )
    proc = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=600,
    )
    return AuditResult(
        package_name=name,
        project_dir=project_dir,
        pyproject=pyproject,
        returncode=proc.returncode,
        stdout=filter_audit_noise(proc.stdout or ""),
        stderr=filter_audit_noise(proc.stderr or ""),
    )


def write_report(
    report_path: Path, repo: Path, results: list[AuditResult], generated_at: datetime
) -> None:
    lines: list[str] = [
        "# pip-audit report (all pyproject projects)",
        "",
        f"Generated: {generated_at.isoformat()}",
        "",
    ]
    for r in sorted(results, key=lambda x: x.package_name.lower()):
        rel_dir = r.project_dir
        try:
            rel_dir = r.project_dir.relative_to(repo)
        except ValueError:
            pass
        lines.append(f"## {r.package_name}")
        lines.append("")
        lines.append(f"- **Path:** `{rel_dir}`")
        lines.append(f"- **Manifest:** `{r.pyproject.name}`")
        lines.append(f"- **Exit code:** {r.returncode}")
        lines.append("")
        out = (r.stdout + r.stderr).strip()
        lines.append("```")
        lines.append(out if out else "(no output)")
        lines.append("```")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=max(1, min(16, (os.cpu_count() or 4) * 2)),
        help="Max concurrent audits (default: based on CPU count, capped at 16)",
    )
    parser.add_argument(
        "--uv",
        default="uv",
        help="uv executable name or path (default: uv)",
    )
    parser.add_argument(
        "--bare",
        action="store_true",
        help="Run `uv run pip-audit` only (no --with pip-audit); requires pip-audit in the project",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=f"Report path (default: <repo root>/{REPORT_FILENAME})",
    )
    args = parser.parse_args()

    root = repo_root()
    out_path = args.output if args.output is not None else root / REPORT_FILENAME
    pyprojects = discover_pyprojects(root)
    if not pyprojects:
        print("No pyproject.toml / pyproject.yaml found.", file=sys.stderr)
        return 2

    generated_at = datetime.now(timezone.utc)
    results: list[AuditResult] = []

    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futures = {
            ex.submit(run_one, pp, args.uv, args.bare): pp for pp in pyprojects
        }
        done = 0
        total = len(futures)
        for fut in as_completed(futures):
            pp = futures[fut]
            try:
                r = fut.result()
                results.append(r)
            except subprocess.TimeoutExpired:
                r = AuditResult(
                    package_name=package_label(pp),
                    project_dir=pp.parent,
                    pyproject=pp,
                    returncode=124,
                    stdout="",
                    stderr="pip-audit timed out after 600s",
                )
                results.append(r)
            except Exception as e:  # noqa: BLE001
                r = AuditResult(
                    package_name=package_label(pp),
                    project_dir=pp.parent,
                    pyproject=pp,
                    returncode=1,
                    stdout="",
                    stderr=f"Error running pip-audit: {e}",
                )
                results.append(r)
            done += 1
            note = "ok" if r.returncode == 0 else f"exit {r.returncode}"
            print(
                f"[pip-audit] {done}/{total} {r.package_name} — {note}",
                flush=True,
            )

    write_report(out_path, root, results, generated_at)
    print(f"Wrote {out_path}")
    return 0 if all(r.returncode == 0 for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
