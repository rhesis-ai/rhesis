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
    rows = [
        [
            row["name"],
            f"{row['requirements_tested']} of {row['requirements_total']}",
            row["failed"],
            kit.pass_rate_text(row.get("pass_rate")),
        ]
        for row in impacts
    ]
    fail = [(i, 2) for i, row in enumerate(impacts) if row["failed"]]
    return [
        *kit.heading("By impact", "Only impacts with a requirement tested in this report."),
        kit.data_table(
            ["Impact", "Requirements tested", "Failed", "Pass rate"],
            rows,
            widths=[0.45, 0.25, 0.12, 0.18],
            right=[2, 3],
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
            ],
            columns=2,
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
