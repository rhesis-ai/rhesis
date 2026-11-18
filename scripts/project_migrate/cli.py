"""Copy a Rhesis project to another Rhesis instance.

  snapshot  read the source project into a JSON file (the only command that reads the source)
  plan      dry run against the target: what would be created, updated or linked
  apply     write to the target; resumable and safe to run again
  verify    plan, then fail unless nothing is left to do and the counts match

API keys come from env only: RHESIS_SRC_API_KEY and RHESIS_DST_API_KEY. The target project
must already exist.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from project_migrate.api import Abort, Api
from project_migrate.engine import Migration, Report
from project_migrate.snapshot import FORMAT_VERSION, summary, take_snapshot
from project_migrate.state import State
from project_migrate.steps import cases, config, sets

REPO_ROOT = Path(__file__).resolve().parents[2]
# Gitignored and shared by every worktree. Snapshots hold customer test data: never commit them.
DEFAULT_WORK_DIR = REPO_ROOT / "playground" / "project-migrate"

STEPS: list[Callable[[Migration], None]] = [
    config.endpoints,
    config.requirements,
    config.metrics,
    config.requirement_metric_links,
    config.topics_and_categories,
    cases.tests,
    sets.test_sets,
]


def env_key(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise Abort(f"set {name}")
    return value


def slug(url: str, project: str) -> str:
    return f"{urlparse(url).hostname or 'host'}-{project}"


def make_api(args: argparse.Namespace, side: str) -> Api:
    url, project = getattr(args, f"{side}_url"), getattr(args, f"{side}_project")
    key = env_key(f"RHESIS_{side.upper()}_API_KEY")
    return Api(url, key, project, read_rps=args.read_rps, write_rps=args.write_rps, label=side)


def load_snapshot(path: str) -> dict:
    snap = json.loads(Path(path).read_text())
    # Snapshots from before format_version existed have the same shape as version 1.
    version = snap.get("format_version", 1)
    if version != FORMAT_VERSION:
        raise Abort(f"snapshot format {version} is not supported (expected {FORMAT_VERSION})")
    return snap


def run_migration(
    snap: dict, dst: Api, state: State, *, dry: bool, limit: int | None, log=print
) -> Report:
    m = Migration(snap, dst, state, dry=dry, limit=limit, log=log)
    config.preflight(m)
    for step in STEPS:
        log(f"-- {step.__name__}")
        step(m)
    return m.report


def cmd_snapshot(args: argparse.Namespace) -> int:
    src = make_api(args, "src")
    snap = take_snapshot(src)
    out = Path(args.work_dir) / "snapshots" / slug(args.src_url, args.src_project)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(snap, indent=1, ensure_ascii=False, default=str))
    print(f"  {summary(snap)}\n  reads={src.calls['read']}\nWrote {path}")
    return 0


def _sync(args: argparse.Namespace, dry: bool) -> tuple[Report, dict, Api]:
    snap = load_snapshot(args.snapshot)
    dst = make_api(args, "dst")
    state = State(
        Path(args.work_dir) / "state" / f"{slug(args.dst_url, args.dst_project)}.json", dry
    )
    if not dry:
        state.lock()
        state.data["src"] = snap["meta"]
        state.save()
    try:
        report = run_migration(snap, dst, state, dry=dry, limit=args.limit)
    finally:
        state.save()
        print(f"\nrequests: reads={dst.calls['read']} writes={dst.calls['write']}")
    print("\n" + report.render())
    if not dry:
        print(f"\nState: {state.path}")
    return report, snap, dst


def cmd_plan(args: argparse.Namespace) -> int:
    _sync(args, dry=True)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    _sync(args, dry=False)
    return 0


def count_table(snap: dict, dst: Api) -> list[tuple[str, int, int]]:
    pf = dst.project_filter()
    return [
        ("endpoints", len(snap["endpoints"]), len(dst.get_all("/endpoints/", **pf))),
        ("requirements", len(snap["requirements"]), len(dst.get_all("/requirements/", **pf))),
        ("custom metrics", len(snap["metrics"]), len(dst.get_all("/metrics/", **pf))),
        ("tests", len(snap["tests"]), len(dst.get_all("/tests/", **pf))),
        ("test sets", len(snap["test_sets"]), len(dst.get_all("/test_sets/", **pf))),
    ]


def cmd_verify(args: argparse.Namespace) -> int:
    report, snap, dst = _sync(args, dry=True)
    counts = count_table(snap, dst)
    print(f"\n{'':<16}{'source':>8}{'target':>8}")
    for name, s, d in counts:
        print(f"{name:<16}{s:>8}{d:>8}{'' if s == d else '   <-- differs'}")
    left = report.pending_work()
    if left or any(s != d for _, s, d in counts):
        print(f"\nVERIFY FAILED: {left} action(s) still pending, or the counts differ")
        return 1
    print("\nVERIFY OK: the target matches the snapshot")
    return 0


def positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be 1 or more")
    return n


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="./rh project-migrate",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--read-rps", type=float, default=5.0, help="max reads per second per host")
    p.add_argument("--write-rps", type=float, default=2.0, help="max writes per second")
    p.add_argument("--work-dir", default=str(DEFAULT_WORK_DIR), help="snapshots and state")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="read the source project into a JSON file")
    s.add_argument("--src-url", required=True)
    s.add_argument("--src-project", required=True)
    s.set_defaults(fn=cmd_snapshot)

    for name, fn, text in (
        ("plan", cmd_plan, "dry run against the target"),
        ("apply", cmd_apply, "write to the target"),
        ("verify", cmd_verify, "check the target matches the snapshot"),
    ):
        c = sub.add_parser(name, help=text)
        c.add_argument("--snapshot", required=True)
        c.add_argument("--dst-url", required=True)
        c.add_argument("--dst-project", required=True)
        c.add_argument("--limit", type=positive_int, help="only the first N tests (trial runs)")
        c.set_defaults(fn=fn)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        sys.exit(args.fn(args))
    except Abort as e:
        print(f"\nABORTED: {e}", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print("\nInterrupted. State is saved; run apply again to resume.", file=sys.stderr)
        sys.exit(130)
