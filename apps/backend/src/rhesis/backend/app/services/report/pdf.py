"""The report as a PDF, built server-side from the same data the page shows.

A published report prints its frozen snapshot, with the snapshot hash on every page
so the file can be checked against the report. A draft prints its live numbers and
says DRAFT on every page.
"""

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy.orm import Session

from rhesis.backend.app import models
from rhesis.backend.app.services.report import pdf_kit as kit
from rhesis.backend.app.services.report.sections import (
    PdfBrand,
    pdf_brand,
    pdf_flowables,
    pdf_notes,
)

logger = logging.getLogger(__name__)

# The requirements table shows this much of each description, so a row stays short.
DESCRIPTION_CHARS = 70

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


def _brand(report: models.Report, brand: PdfBrand) -> Paragraph:
    kind = "RELEASE REPORT" if report.is_release else "REPORT"
    line = kit.text(f"{brand.name.upper()} · {kind}")
    return Paragraph(f'<font color="{brand.color}">{line}</font>', kit.STYLES["brand"])


def _header(report: models.Report, detail: Dict[str, Any], brand: PdfBrand) -> List[Any]:
    endpoint = (detail.get("endpoint") or {}).get("name") or "Unknown endpoint"
    author = (report.user.name or report.user.email) if report.user else "Unknown author"
    if report.is_published and report.published_at:
        state = f"Published {report.published_at:%d %B %Y}"
    else:
        state = "Draft, numbers not frozen"
    return [
        _brand(report, brand),
        Spacer(1, 4),
        Paragraph(kit.text(report.title), kit.STYLES["title"]),
        Paragraph(kit.text(f"{endpoint} · {state} · by {author}"), kit.STYLES["subtitle"]),
        Spacer(1, 14),
    ]


def _details_header(report: models.Report, brand: PdfBrand) -> List[Any]:
    return [
        _brand(report, brand),
        Spacer(1, 4),
        Paragraph("Details", kit.STYLES["title"]),
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
    cells = {
        "tests": (
            "Results" if rule == "all" else "Tests",
            lambda r, t: f"{r['tests']}*" if r.get("low_sample") else (r["tests"] or ""),
        ),
        "failed": ("Failed", lambda r, t: r["failed"] if t else ""),
        "mixed": ("Mixed", lambda r, t: r.get("inconsistent") or ""),
        "pass_rate": (
            "Pass rate",
            lambda r, t: kit.pass_rate_text(r.get("pass_rate")) if t else UNTESTED[r["coverage"]],
        ),
        "change": ("Change", lambda r, t: _delta_text(r.get("pass_rate_delta"))),
        "bar": ("", lambda r, t: kit.rate_bar(r.get("pass_rate")) if t else ""),
    }
    scores = [
        (cells[key][0], kit.SCORE_WIDTHS[key], key != "bar", cells[key][1])
        for key in kit.score_columns(rule, compared)
    ]
    # The requirement name takes whatever width is left.
    name_width = 1 - sum(c[1] for c in scores)
    return [("Requirement", name_width, False, lambda r, t: r["name"]), *scores]


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
    table_rows, bold, indent, fail, subtitles = [], [], [], [], {}
    for i, row in enumerate(rows):
        tested = row["coverage"] == "tested"
        subtitles[i] = kit.shorten(row.get("description"), DESCRIPTION_CHARS)
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
            subtitles=subtitles,
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
    # Only when some run used an experiment: an empty column is noise.
    with_experiment = any(run.get("experiment") for run in runs)
    rows = []
    for run in runs:
        row = [run.get("name") or run["id"], run.get("test_set") or "—"]
        if with_experiment:
            row.append(experiment_label(run.get("experiment")))
        row += [
            run.get("status") or "—",
            _day(run.get("created_at")),
            run.get("results", 0),
            kit.pass_rate_text(run.get("pass_rate")),
        ]
        rows.append(row)
    note = RULE_NOTES.get(rule, "")
    spread = run_rate_spread(runs)
    if rule == "all" and spread:
        note += f" Run pass rates range from {spread}."
    if with_experiment:
        headers = ["Run", "Test set", "Experiment", "Status", "Started", "Counted", "Pass rate"]
        widths = [0.15, 0.22, 0.14, 0.13, 0.13, 0.11, 0.12]
        right = [5, 6]
    else:
        headers = ["Run", "Test set", "Status", "Started", "Counted", "Pass rate"]
        widths = [0.2, 0.31, 0.13, 0.13, 0.11, 0.12]
        right = [4, 5]
    return [
        *kit.heading("Test runs", note),
        kit.data_table(headers, rows, widths=widths, right=right),
    ]


def experiment_label(experiment: Optional[Dict[str, Any]]) -> str:
    """'Low temp v2'; '—' for a run without an experiment."""
    if not experiment:
        return "—"
    return " ".join(filter(None, [experiment.get("name"), experiment.get("version")]))


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


def _page_decorator(report: models.Report, brand: PdfBrand):
    logo = _logo(brand.logo)

    footer = (
        f"{report.title} · snapshot {report.snapshot_hash}"
        if report.is_published
        else f"{report.title} · DRAFT, numbers not frozen"
    )

    def draw(canvas, doc) -> None:
        canvas.saveState()
        if logo is not None:
            # Top-right, inside the top margin: at most 8 mm high, 40 mm wide.
            width, height = logo.getSize()
            scale = min(8 * mm / height, 40 * mm / width)
            w, h = width * scale, height * scale
            canvas.drawImage(logo, A4[0] - 15 * mm - w, A4[1] - 5 * mm - h, w, h, mask="auto")
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


def _logo(data: Optional[bytes]) -> Optional[ImageReader]:
    if not data:
        return None
    try:
        return ImageReader(io.BytesIO(data))
    except Exception:
        logger.warning("report PDF logo could not be read; leaving it out")
        return None


def render_report_pdf(
    db: Session,
    report: models.Report,
    detail: Dict[str, Any],
    organization: Optional[models.Organization],
) -> bytes:
    """``detail`` is what the page shows: frozen for a published report, live for a draft."""
    metrics = detail.get("metrics") or {}
    sections = detail.get("sections") or {}
    brand = pdf_brand(db, organization)
    story: List[Any] = [
        *_header(report, detail, brand),
        *_summary(report, metrics),
        *_decision_notes(metrics),
        *pdf_flowables(sections, organization, "after_summary", frozen=report.is_published),
        *_requirements(metrics),
        # Page 1 is the summary; the details follow on their own pages.
        PageBreak(),
        *_details_header(report, brand),
        *_runs(metrics),
        *_metric_results(metrics),
        *pdf_flowables(sections, organization, "details", frozen=report.is_published),
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
        author=brand.name,
    )
    draw = _page_decorator(report, brand)
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()
