"""How the EE sections and the audit line print in a report PDF."""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.features import FeatureName, FeatureRegistry
from rhesis.backend.app.services.report import pdf_kit as kit
from rhesis.backend.ee.audit import crud as audit_crud


def render_by_impact(data: Dict[str, Any]) -> List[Any]:
    impacts = data.get("impacts") or []
    if not impacts:
        return []
    rule = data.get("result_rule", "latest")
    # Same score columns as the requirements table below, so the two line up;
    # Mixed and Change stay blank here.
    keys = kit.score_columns(rule, bool(data.get("compared")))
    headers = {
        "tests": "Results" if rule == "all" else "Tests",
        "failed": "Failed",
        "mixed": "",
        "pass_rate": "Pass rate",
        "change": "",
        "bar": "",
    }

    def score(row: Dict[str, Any], key: str) -> Any:
        if key == "tests":
            return row.get("tests", "")
        if key == "failed":
            return row["failed"]
        if key == "pass_rate":
            return kit.pass_rate_text(row.get("pass_rate"))
        if key == "bar":
            return kit.rate_bar(row.get("pass_rate"))
        return ""

    rows = [
        [
            row["name"],
            f"{row['requirements_tested']} of {row['requirements_total']}",
            *[score(row, key) for key in keys],
        ]
        for row in impacts
    ]
    failed_col = 2 + keys.index("failed")
    fail = [(i, failed_col) for i, row in enumerate(impacts) if row["failed"]]
    score_widths = [kit.SCORE_WIDTHS[key] for key in keys]
    # Impact and Requirements tested share the width the requirement name gets below.
    lead = 1 - sum(score_widths)
    return [
        *kit.heading("By impact", "Only impacts with a requirement tested in this report."),
        kit.data_table(
            ["Impact", "Requirements tested", *[headers[key] for key in keys]],
            rows,
            widths=[lead * 0.55, lead * 0.45, *score_widths],
            right=[2 + i for i, key in enumerate(keys) if key != "bar"],
            fail_cells=fail,
        ),
    ]


def _names(people: List[Dict[str, Any]]) -> str:
    return ", ".join(p["name"] for p in people) or "—"


def render_people(data: Dict[str, Any]) -> List[Any]:
    reviewed = _names(data.get("reviewers") or [])
    if data.get("reviewers"):
        changed = data.get("verdicts_changed", 0)
        reviewed += f" · {changed} verdict{'' if changed == 1 else 's'} changed"
    author = (data.get("author") or {}).get("name") or "—"
    return [
        *kit.heading("Who was involved"),
        kit.fields(
            [
                ("Author", author),
                ("Ran the tests", _names(data.get("ran_tests") or [])),
                ("Reviewed results", reviewed),
            ]
        ),
    ]


def render_stats(data: Dict[str, Any]) -> List[Any]:
    times = data.get("response_time_ms")
    judged = data.get("results_judged", 0)
    errored = data.get("results_errored", 0)
    timing = (
        f"{times['mean'] / 1000:.1f} s / {times['p95'] / 1000:.1f} s" if times else "Not measured"
    )
    return [
        *kit.heading("Stats"),
        kit.fields(
            [
                ("Results", f"{judged} judged · {errored} errored"),
                ("Response time, mean / p95", timing),
            ]
        ),
    ]


def audit_note(db: Session, report: models.Report) -> Optional[str]:
    """'Recorded in audit log on ...' for a published report, with the audit log."""
    if not report.is_published:
        return None
    organization = db.get(models.Organization, report.organization_id)
    if not FeatureRegistry.is_available(FeatureName.AUDIT_LOG, organization):
        return None
    events = audit_crud.list_audit_events(
        db,
        str(report.organization_id),
        limit=1,
        sort_order="asc",
        filter=f"resource_id eq {report.id} and action eq 'report.published'",
    )
    if not events:
        return "Not in the audit log (published before it was enabled, or removed by retention)"
    return f"Recorded in audit log on {events[0].occurred_at:%d %b %Y, %H:%M} UTC"
