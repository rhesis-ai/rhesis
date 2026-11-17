"""The report as a PDF, built server-side from the same data the page shows.

A published report prints its frozen snapshot, with the snapshot hash on every page
so the file can be checked against the report. A draft prints its live numbers and
says DRAFT on every page.
"""

import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer
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


RECOMMENDATION_TONES = {"ready": "good", "ready_with_risks": "warn", "not_ready": "bad"}


def _brand(report: models.Report) -> str:
    return "RHESIS · RELEASE REPORT" if report.is_release else "RHESIS · REPORT"


def _header(report: models.Report, detail: Dict[str, Any]) -> List[Any]:
    endpoint = (detail.get("endpoint") or {}).get("name") or "Unknown endpoint"
    author = (report.user.name or report.user.email) if report.user else "Unknown author"
    if report.is_published and report.published_at:
        state = f"Published {report.published_at:%d %B %Y}"
    else:
        state = "Draft, numbers not frozen"
    return [
        Paragraph(_brand(report), kit.STYLES["brand"]),
        Spacer(1, 4),
        Paragraph(kit.text(report.title), kit.STYLES["title"]),
        Paragraph(kit.text(f"{endpoint} · {state} · by {author}"), kit.STYLES["subtitle"]),
        Spacer(1, 14),
    ]


def _details_header(report: models.Report) -> List[Any]:
    return [
        Paragraph(_brand(report), kit.STYLES["brand"]),
        Spacer(1, 4),
        Paragraph("Details", kit.STYLES["title"]),
        Paragraph(
            kit.text(f"{report.title}: the runs, the people and the record behind the summary."),
            kit.STYLES["subtitle"],
        ),
        Spacer(1, 6),
    ]


def _summary(report: models.Report, metrics: Dict[str, Any]) -> List[Any]:
    totals = metrics.get("totals", {})
    runs = metrics.get("runs", [])
    out: List[Any] = []
    if report.is_release and report.recommendation:
        out += [
            kit.callout(
                "Recommendation",
                RECOMMENDATIONS[report.recommendation],
                RECOMMENDATION_TONES[report.recommendation],
            ),
            Spacer(1, 14),
        ]
    comparison = metrics.get("comparison") or {}
    delta = comparison.get("pass_rate_delta")
    figures = [
        (
            "Pass rate"
            + (
                f", {_delta_text(delta)} pts vs {comparison['baseline']['title']}"
                if delta is not None
                else ""
            ),
            kit.pass_rate_text(totals.get("pass_rate")),
        ),
        (
            "Results" + (f", {totals['errored']} errored" if totals.get("errored") else ""),
            str(totals.get("results", 0)),
        ),
        ("Test runs", str(len(runs))),
        (
            "Requirements tested",
            f"{totals.get('requirements_tested', 0)} of {totals.get('requirements_total', 0)}",
        ),
    ]
    if metrics.get("result_rule", "latest") != "latest":
        figures.append(("Mixed results", str(totals.get("inconsistent", 0))))
    out += [kit.figures(figures), Spacer(1, 4)]
    out += kit.heading("Summary")
    out += kit.prose(report.summary, "No summary written.")
    if metrics.get("versions_differ"):
        out.append(
            Paragraph(
                "Note: the runs in this report tested different endpoint versions.",
                kit.STYLES["small"],
            )
        )
    return out


def _delta_text(delta: Optional[float]) -> str:
    if delta is None:
        return "—"
    if abs(delta) < 0.05:
        return "±0.0"
    return f"{delta:+.1f}".replace("-", "−")


def _requirement_columns(rule: str, compared: bool) -> List[tuple]:
    """(header, width, right-aligned, cell) per column; cell(row, tested) -> value."""
    columns = [
        ("Requirement", 0.36, False, lambda r, t: r["name"]),
        (
            "Results" if rule == "all" else "Tests",
            0.1,
            True,
            lambda r, t: f"{r['tests']}*" if r.get("low_sample") else (r["tests"] or ""),
        ),
        ("Failed", 0.1, True, lambda r, t: r["failed"] if t else ""),
    ]
    if rule != "latest":
        columns.append(("Mixed", 0.09, True, lambda r, t: r.get("inconsistent") or ""))
    columns.append(
        (
            "Pass rate",
            0.12,
            True,
            lambda r, t: kit.pass_rate_text(r.get("pass_rate")) if t else UNTESTED[r["coverage"]],
        )
    )
    if compared:
        columns.append(("Change", 0.1, True, lambda r, t: _delta_text(r.get("pass_rate_delta"))))
    columns.append(("", 0.13, False, lambda r, t: kit.rate_bar(r.get("pass_rate")) if t else ""))
    # Give whatever width is left to the requirement name.
    spare = 1 - sum(c[1] for c in columns)
    columns[0] = (columns[0][0], columns[0][1] + spare, False, columns[0][3])
    return columns


def _requirements(metrics: Dict[str, Any]) -> List[Any]:
    rows = metrics.get("requirements", [])
    rule = metrics.get("result_rule", "latest")
    compared = metrics.get("comparison") is not None
    out = kit.heading("Requirements")
    if not rows:
        return [*out, Paragraph("No requirements picked.", kit.STYLES["small"])]
    columns = _requirement_columns(rule, compared)
    failed_col = [c[0] for c in columns].index("Failed")
    delta_col = [c[0] for c in columns].index("Change") if compared else None
    table_rows, bold, indent, fail = [], [], [], []
    for i, row in enumerate(rows):
        tested = row["coverage"] == "tested"
        table_rows.append([cell(row, tested) for *_, cell in columns])
        (bold if row["level"] == 0 else indent).append(i)
        if tested and row["failed"]:
            fail.append((i, failed_col))
        if delta_col is not None and (row.get("pass_rate_delta") or 0) <= -0.05:
            fail.append((i, delta_col))
    notes = []
    if rule != "latest":
        notes.append("Mixed: tests that passed in some runs and failed in others.")
    if any(row.get("low_sample") for row in rows):
        notes.append("* Fewer than 10 results: read the pass rate with care.")
    if compared:
        title = metrics["comparison"]["baseline"]["title"]
        notes.append(f"Change: percentage points against {title}.")
    out += (
        [Paragraph(kit.text(" ".join(notes)), kit.STYLES["small"]), Spacer(1, 4)] if notes else []
    )
    return [
        *out,
        kit.data_table(
            [c[0] for c in columns],
            table_rows,
            widths=[c[1] for c in columns],
            right=[i for i, c in enumerate(columns) if c[2]],
            bold_rows=bold,
            indent_rows=indent,
            fail_cells=fail,
        ),
    ]


def _decision_notes(metrics: Dict[str, Any]) -> List[Any]:
    """Comparison with the previous report, then the caveats."""
    lines = []
    comparison = metrics.get("comparison")
    if comparison:
        baseline = comparison["baseline"]
        line = (
            f"Compared with {baseline['title']}: {comparison['newly_failing']} tests newly failing"
        )
        if comparison.get("newly_failing_requirements"):
            line += f" ({', '.join(comparison['newly_failing_requirements'][:4])})"
        line += f", {comparison['fixed']} fixed."
        if baseline.get("result_rule") != metrics.get("result_rule"):
            line += " The previous report counted results differently."
        lines.append(line)
    lines += [w["text"] for w in metrics.get("warnings") or []]
    if not lines:
        return []
    return [*kit.heading("Before you decide"), kit.bullets(lines)]


def _runs(metrics: Dict[str, Any]) -> List[Any]:
    runs = metrics.get("runs", [])
    rule = metrics.get("result_rule", "latest")
    rows = [
        [
            run.get("name") or run["id"],
            run.get("test_set") or "—",
            run.get("status") or "—",
            _day(run.get("created_at")),
            run.get("results", 0),
            kit.pass_rate_text(run.get("pass_rate")),
        ]
        for run in runs
    ]
    note = RULE_NOTES.get(rule, "")
    spread = run_rate_spread(runs)
    if rule == "all" and spread:
        note += f" Run pass rates range from {spread}."
    return [
        *kit.heading("Test runs", note),
        kit.data_table(
            ["Run", "Test set", "Status", "Started", "Counted", "Pass rate"],
            rows,
            widths=[0.2, 0.31, 0.13, 0.13, 0.11, 0.12],
            right=[4, 5],
        ),
    ]


def _day(value: Any) -> str:
    """'23 Oct 2026' from an ISO timestamp or datetime; '—' when missing."""
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value)).strftime("%d %b %Y")
    except ValueError:
        return str(value)[:10]


def run_rate_spread(runs: List[Dict[str, Any]]) -> Optional[str]:
    """'0.0% to 100.0%' over the runs that judged something; None with fewer than two."""
    rates = [r["pass_rate"] for r in runs if r.get("pass_rate") is not None]
    if len(rates) < 2:
        return None
    return f"{kit.pass_rate_text(min(rates))} to {kit.pass_rate_text(max(rates))}"


METRIC_KINDS = {"llm": "LLM", "jev": "JEV", "code": "Code"}


def _metric_results(metrics: Dict[str, Any]) -> List[Any]:
    groups = metrics.get("metric_results") or []
    if not groups:
        return []
    rows, bold, indent, fail = [], [], [], []
    for group in groups:
        bold.append(len(rows))
        rows.append([group["name"], "", "", "", ""])
        for metric in group["metrics"]:
            indent.append(len(rows))
            if metric["failed"]:
                fail.append((len(rows), 3))
            rows.append(
                [
                    metric["name"],
                    METRIC_KINDS.get(metric["kind"], metric["kind"]),
                    metric["passed"],
                    metric["failed"],
                    kit.pass_rate_text(metric.get("pass_rate")),
                ]
            )
    return [
        *kit.heading(
            "Metrics by requirement",
            "How each metric judged the requirement's results. LLM: an LLM judge. "
            "JEV: a classifier with a Jev model. Code: a code check.",
        ),
        kit.data_table(
            ["Requirement / metric", "Kind", "Passed", "Failed", "Pass rate"],
            rows,
            widths=[0.5, 0.12, 0.12, 0.12, 0.14],
            right=[2, 3, 4],
            bold_rows=bold,
            indent_rows=indent,
            fail_cells=fail,
        ),
    ]


def _record(report: models.Report, notes: List[str]) -> List[Any]:
    """The proof of what was approved: a short line block at the end, not a section."""
    if not report.is_published:
        return []
    lines = [f"Snapshot hash {report.snapshot_hash}", *notes]
    return [
        Spacer(1, 18),
        HRFlowable(width="100%", thickness=0.3, color=kit.BORDER, spaceAfter=4),
        *[Paragraph(kit.text(line), kit.STYLES["small"]) for line in lines],
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
        *_decision_notes(metrics),
        *pdf_flowables(sections, organization, "after_summary"),
        *_requirements(metrics),
        # Page 1 is the summary; the details follow on their own pages.
        PageBreak(),
        *_details_header(report),
        *_runs(metrics),
        *_metric_results(metrics),
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
