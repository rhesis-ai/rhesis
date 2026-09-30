"""Run the eval set against the real model and report route accuracy and page recall.

    uv run python examples/run_evals.py
    uv run python examples/run_evals.py --only sdk-install,helm --no-save

Each row names an expected route and the pages a good answer cites. An entry like
"docs/metrics/metric-scope|sdk/metrics" means either page counts. Results are saved to
evals/last_run.json and the next run is compared against it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
EVAL_SET = ROOT / "evals" / "starter_set.jsonl"
LAST_RUN = ROOT / "evals" / "last_run.json"


@dataclass
class RowResult:
    id: str
    expected_route: str
    route: str
    route_ok: bool
    page_recall: float | None
    cited: list[str]
    limits_hit: list[str]
    seconds: float


def load_rows(path: Path = EVAL_SET) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def page_recall(expected_pages: list[str], cited_urls: list[str]) -> float | None:
    """Share of expected pages cited; each entry may list alternatives separated by `|`."""
    if not expected_pages:
        return None
    cited = {url.split("#", 1)[0].removeprefix("https://docs.rhesis.ai/") for url in cited_urls}
    hits = sum(1 for group in expected_pages if cited & set(group.split("|")))
    return hits / len(expected_pages)


def route_ok(row: dict, route: str) -> bool:
    return route in {row["expected_route"], *row.get("also_ok", [])}


def summarize(results: list[RowResult]) -> dict:
    recalls = [r.page_recall for r in results if r.page_recall is not None]
    return {
        "rows": len(results),
        "route_correct": sum(r.route_ok for r in results),
        "route_accuracy": sum(r.route_ok for r in results) / max(len(results), 1),
        "page_recall": sum(recalls) / len(recalls) if recalls else None,
        "mean_seconds": sum(r.seconds for r in results) / max(len(results), 1),
    }


async def run_row(row: dict, cache) -> RowResult:
    from docs_assistant.runner import run_turn

    start = time.perf_counter()
    response = await run_turn(row["question"], cache=cache)
    cited = [c.url for c in response.citations]
    return RowResult(
        id=row["id"],
        expected_route=row["expected_route"],
        route=response.route.value,
        route_ok=route_ok(row, response.route.value),
        page_recall=page_recall(row["expected_pages"], cited),
        cited=cited,
        limits_hit=response.limits_hit,
        seconds=round(time.perf_counter() - start, 1),
    )


def print_report(results: list[RowResult], summary: dict, previous: dict | None) -> None:
    before = {r["id"]: r for r in (previous or {}).get("results", [])}
    print(f"{'row':18} {'expected':20} {'got':20} {'recall':>6} {'secs':>5}  change")
    for r in results:
        recall = "-" if r.page_recall is None else f"{r.page_recall:.2f}"
        mark = "ok " if r.route_ok else "MISS"
        change = _row_change(r, before.get(r.id))
        columns = f"{r.id:18} {r.expected_route:20} {r.route:20} {recall:>6} {r.seconds:5.1f}"
        print(f"{columns}  {mark} {change}")
        if r.limits_hit:
            print(f"{'':18} limits: {', '.join(r.limits_hit)}")
    print()
    print(_summary_line("now", summary))
    if previous:
        print(_summary_line("before", previous["summary"]))


def _row_change(result: RowResult, before: dict | None) -> str:
    if before is None:
        return ""
    if before["route_ok"] != result.route_ok:
        return "fixed" if result.route_ok else "REGRESSED"
    if (before["page_recall"] or 0) != (result.page_recall or 0):
        return f"recall {before['page_recall']} → {result.page_recall}"
    return ""


def _summary_line(label: str, s: dict) -> str:
    recall = "-" if s["page_recall"] is None else f"{s['page_recall']:.2f}"
    return (
        f"{label:6} route accuracy {s['route_correct']}/{s['rows']} ({s['route_accuracy']:.0%}) · "
        f"page recall {recall} · mean {s['mean_seconds']:.1f}s"
    )


async def main_async(args) -> int:
    from docs_assistant.app import make_cache

    rows = load_rows()
    if args.only:
        wanted = set(args.only.split(","))
        rows = [r for r in rows if r["id"] in wanted]
    cache = make_cache()
    await cache.get()
    semaphore = asyncio.Semaphore(args.concurrency)

    async def guarded(row):
        async with semaphore:
            return await run_row(row, cache)

    results = await asyncio.gather(*(guarded(r) for r in rows))
    summary = summarize(results)
    previous = json.loads(LAST_RUN.read_text()) if LAST_RUN.exists() else None
    print_report(results, summary, previous)
    if not args.no_save:
        LAST_RUN.write_text(
            json.dumps({"summary": summary, "results": [asdict(r) for r in results]}, indent=2)
        )
    return 0


def main() -> int:
    load_dotenv(ROOT / ".env")
    sys.path.insert(0, str(ROOT / "src"))
    parser = argparse.ArgumentParser(prog="run_evals.py")
    parser.add_argument("--only", help="comma-separated row ids")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--no-save", action="store_true", help="don't overwrite last_run.json")
    try:
        return asyncio.run(main_async(parser.parse_args()))
    except RuntimeError as exc:
        print(f"Eval run failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
