"""The report as a PDF, built server-side from the same data the page shows.

A published report prints its frozen snapshot, with the snapshot hash on every page
so the file can be checked against the report. A draft prints its live numbers and
says DRAFT on every page.
"""

import io
from typing import Any, Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.report import pdf_kit as kit
from rhesis.backend.app.services.report.sections import pdf_flowables, pdf_notes

RECOMMENDATIONS = {
    "ready": "Ready to ship",
    "ready_with_risks": "Ready to ship, with known risks",
    "not_ready": "Not ready to ship",
}
RULE_NOTES = {
    "latest": "When a test ran in more than one run, the latest run's result counts.",
    "all": "Every result in every run counts: pass rates are averages over the runs.",
    "worst": "A test counts as failed if it failed in any run.",
}
UNTESTED = {
    "no_tests": "No tests yet",
    "not_in_runs": "Not in these runs",
    "errored_only": "Every test errored",
}


def _version(info: Optional[Dict[str, Any]]) -> str:
    if not info:
        return "—"
    return " · ".join(
        f"{k}: {v}" for k, v in info.items() if v is not None and not isinstance(v, (dict, list))
    )


def _header(report: models.Report, detail: Dict[str, Any]) -> List[Any]:
    endpoint = (detail.get("endpoint") or {}).get("name") or "Unknown endpoint"
    author = (report.user.name or report.user.email) if report.user else "Unknown author"
    if report.is_published and report.published_at:
        state = f"Published {report.published_at:%d %b %Y} · numbers frozen"
    else:
        state = "Draft · numbers not frozen"
    return [
        Paragraph(kit.text(report.title), kit.STYLES["title"]),
        Paragraph(
            kit.text(f"Release report · {endpoint} · by {author} · {state}"),
            kit.STYLES["subtitle"],
        ),
        Spacer(1, 6),
    ]


def _summary(report: models.Report, metrics: Dict[str, Any]) -> List[Any]:
    totals = metrics.get("totals", {})
    runs = metrics.get("runs", [])
    results = str(totals.get("results", 0))
    if totals.get("errored"):
        results += f" ({totals['errored']} errored)"
    numbers = kit.fields(
        [
            ("Pass rate", kit.pass_rate_text(totals.get("pass_rate"))),
            ("Results", results),
            ("Runs", str(len(runs))),
            (
                "Requirements tested",
                f"{totals.get('requirements_tested', 0)} of {totals.get('requirements_total', 0)}",
            ),
        ],
        columns=4,
    )
    out: List[Any] = [*kit.heading("Summary"), numbers, Spacer(1, 6)]
    out.append(
        kit.fields(
            [
                ("Recommendation", RECOMMENDATIONS.get(report.recommendation or "", "—")),
                ("Management summary", report.summary or "—"),
            ]
        )
    )
    if metrics.get("versions_differ"):
        out.append(
            Paragraph(
                "The runs in this report tested different endpoint versions.", kit.STYLES["small"]
            )
        )
    return out


def _requirements(metrics: Dict[str, Any]) -> List[Any]:
    rows = metrics.get("requirements", [])
    rule = metrics.get("result_rule", "latest")
    out = kit.heading("Requirements")
    if not rows:
        return [*out, Paragraph("No requirements picked.", kit.STYLES["small"])]
    show_inconsistent = rule != "latest"
    header = ["Requirement", "Results" if rule == "all" else "Tests", "Failed"]
    if show_inconsistent:
        header.append("Inconsistent")
    header.append("Pass rate")
    table_rows, bold, indent, fail = [], [], [], []
    for i, row in enumerate(rows):
        tested = row["coverage"] == "tested"
        cells = [row["name"], row["tests"] or "", row["failed"] if tested else ""]
        if show_inconsistent:
            cells.append(row.get("inconsistent") or "")
        rate = kit.pass_rate_text(row.get("pass_rate")) if tested else UNTESTED[row["coverage"]]
        table_rows.append([*cells, rate])
        (bold if row["level"] == 0 else indent).append(i)
        if tested and row["failed"]:
            fail.append((i, 2))
    widths = [0.45, 0.12, 0.11, 0.13, 0.19] if show_inconsistent else [0.55, 0.12, 0.12, 0.21]
    return [
        *out,
        kit.data_table(
            header,
            table_rows,
            widths=widths,
            right=list(range(1, len(header))),
            bold_rows=bold,
            indent_rows=indent,
            fail_cells=fail,
        ),
    ]


def _runs(metrics: Dict[str, Any]) -> List[Any]:
    runs = metrics.get("runs", [])
    rows = [
        [
            run.get("name") or run["id"],
            str(run.get("created_at") or "")[:16].replace("T", " "),
            _version(run.get("version_info")),
            run.get("results", 0),
        ]
        for run in runs
    ]
    return [
        *kit.heading("Test runs", RULE_NOTES.get(metrics.get("result_rule", ""), "")),
        kit.data_table(
            ["Run", "Started", "Version", "Results"],
            rows,
            widths=[0.4, 0.2, 0.28, 0.12],
            right=[3],
        ),
    ]


def _record(report: models.Report, notes: List[str]) -> List[Any]:
    if not report.is_published:
        return []
    pairs = [("Snapshot hash", report.snapshot_hash or "—")]
    pairs += [("Record", note) for note in notes]
    return [
        *kit.heading("Snapshot", "Hash over everything this report shows."),
        kit.fields(pairs),
    ]


def _page_decorator(report: models.Report):
    footer = (
        f"{report.title} · snapshot {report.snapshot_hash}"
        if report.is_published
        else f"{report.title} · DRAFT, numbers not frozen"
    )

    def draw(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont(kit.FONT, 7)
        canvas.setFillColor(kit.MUTED)
        canvas.drawString(15 * mm, 10 * mm, footer[:150])
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
        if not report.is_published:
            canvas.setFont(kit.FONT_BOLD, 60)
            canvas.setFillColor(kit.BORDER)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, "DRAFT")
        canvas.restoreState()

    return draw


def render_report_pdf(
    db: Session,
    report: models.Report,
    detail: Dict[str, Any],
    organization: Optional[models.Organization],
) -> bytes:
    """``detail`` is what the page shows: frozen for a published report, live for a draft."""
    metrics = detail.get("metrics") or {}
    sections = detail.get("sections") or {}
    story: List[Any] = [
        *_header(report, detail),
        *_summary(report, metrics),
        *pdf_flowables(sections, organization, "after_summary"),
        *_requirements(metrics),
        *_runs(metrics),
        *pdf_flowables(sections, organization, "details"),
        *_record(report, pdf_notes(db, report)),
    ]
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=report.title,
        author="Rhesis",
    )
    draw = _page_decorator(report)
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()
