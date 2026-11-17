"""How each metric judged each requirement's counted results.

A metric is one of three kinds: an LLM judge (custom prompt or framework metric), a JEV
classifier (a judge with a Jev decision model connected), or a code check.
"""

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from rhesis.backend.app.crud import report as report_crud
from rhesis.backend.app.services.report.counting import CountedResult, pass_rate

KIND_LLM = "llm"
KIND_JEV = "jev"
KIND_CODE = "code"


def kind_of(metric_type: Any, provider: Any) -> str:
    if metric_type == "custom-code":
        return KIND_CODE
    if provider == "jev":
        return KIND_JEV
    return KIND_LLM


def _verdicts(test_metrics: Any) -> Dict[str, bool]:
    """``{metric name: passed}`` for the metrics that reached a verdict."""
    metrics = test_metrics.get("metrics") if isinstance(test_metrics, dict) else None
    if not isinstance(metrics, dict):
        return {}
    return {
        name: value["is_successful"]
        for name, value in metrics.items()
        if isinstance(value, dict) and isinstance(value.get("is_successful"), bool)
    }


def metrics_by_requirement(
    db: Session, counted: List[CountedResult], tree: List[dict]
) -> List[Dict[str, Any]]:
    """Per requirement (tree order), its metrics' pass and fail counts, weakest first."""
    stored = report_crud.get_result_metrics(db, [r.test_result_id for r in counted])
    tallies: Dict[Any, Dict[str, List[int]]] = {}
    for result in counted:
        if result.execution != "ok" or result.requirement_id is None:
            continue
        per_metric = tallies.setdefault(result.requirement_id, {})
        for name, passed in _verdicts(stored.get(result.test_result_id)).items():
            per_metric.setdefault(name, [0, 0])[0 if passed else 1] += 1

    kinds = report_crud.get_metric_kinds(
        db, [name for per_metric in tallies.values() for name in per_metric]
    )
    out = []
    for row in tree:
        per_metric = tallies.get(row["id"])
        if not per_metric:
            continue
        metrics = [
            {
                "name": name,
                "kind": kind_of(*kinds.get(name, (None, None))),
                "passed": passed,
                "failed": failed,
                "pass_rate": pass_rate(passed, failed),
            }
            for name, (passed, failed) in per_metric.items()
        ]
        metrics.sort(key=lambda m: (m["pass_rate"] is None, m["pass_rate"] or 0, m["name"]))
        out.append(
            {
                "requirement_id": row["id"],
                "name": row["name"],
                "level": row["level"],
                "metrics": metrics,
            }
        )
    return out
