"""What a decision-maker needs beyond the totals: the caveats. Pure over what
``service`` already computed."""

from typing import Dict, List

from rhesis.backend.app.services.report.counting import CountedResult

# A requirement judged on fewer results than this gets a low-sample flag.
LOW_SAMPLE = 10
COMPLETED = "completed"


def _names(rows: List[dict], limit: int = 4) -> str:
    names = [row["name"] for row in rows[:limit]]
    more = len(rows) - limit
    return ", ".join(names) + (f" and {more} more" if more > 0 else "")


def warnings(
    tree: List[dict], runs: List[dict], counted: List[CountedResult], totals: dict
) -> List[Dict[str, str]]:
    """The caveats a reader should know before trusting the numbers."""
    out: List[Dict[str, str]] = []
    untested = [r for r in tree if r["coverage"] != "tested"]
    if untested:
        out.append({"kind": "untested", "text": f"Not tested: {_names(untested)}."})
    incomplete = [r for r in runs if (r.get("status") or COMPLETED).lower() != COMPLETED]
    if incomplete:
        listed = ", ".join(f"{r.get('name') or r['id']} ({r.get('status')})" for r in incomplete)
        out.append({"kind": "incomplete_runs", "text": f"Runs that didn't complete: {listed}."})
    low = [r for r in tree if r["coverage"] == "tested" and r["tests"] < LOW_SAMPLE]
    if low:
        out.append(
            {
                "kind": "low_sample",
                "text": f"Fewer than {LOW_SAMPLE} results, so read their pass rates with care: "
                f"{_names(low)}.",
            }
        )
    changed = sum(1 for r in counted if r.overridden)
    if changed:
        out.append(
            {
                "kind": "verdicts_changed",
                "text": f"Reviewers changed {changed} of the judges' verdicts.",
            }
        )
    if totals.get("errored"):
        out.append(
            {
                "kind": "errored",
                "text": f"{totals['errored']} results errored and aren't in the pass rate.",
            }
        )
    return out


def flag_low_samples(tree: List[dict]) -> None:
    for row in tree:
        row["low_sample"] = row["coverage"] == "tested" and row["tests"] < LOW_SAMPLE
