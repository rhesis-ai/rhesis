"""The building blocks of a report PDF, shared with registered sections so they print alike.

The look is a document, not a form: prose for text, large figures for the key
numbers, ruled tables with a pass-rate bar, and a quiet label/value list for details.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    KeepTogether,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

PRIMARY = colors.HexColor("#0080af")
TEXT = colors.HexColor("#16232c")
MUTED_HEX = "#5a6b77"
MUTED = colors.HexColor(MUTED_HEX)
BORDER = colors.HexColor("#dbe3e9")
TRACK = colors.HexColor("#eef3f6")
FAIL_HEX = "#b52a47"
FAIL = colors.HexColor(FAIL_HEX)
GOOD = colors.HexColor("#1f7a5c")
WARN = colors.HexColor("#8f5500")

# Helvetica covers Latin-1 only. The backend image installs DejaVu (fonts-dejavu-core)
# for everything else; without it (e.g. local dev on macOS) PDFs fall back to Helvetica.
_DEJAVU_DIR = Path("/usr/share/fonts/truetype/dejavu")


def _register_fonts() -> Tuple[str, str]:
    regular, bold = _DEJAVU_DIR / "DejaVuSans.ttf", _DEJAVU_DIR / "DejaVuSans-Bold.ttf"
    if not (regular.exists() and bold.exists()):
        return "Helvetica", "Helvetica-Bold"
    pdfmetrics.registerFont(TTFont("DejaVuSans", str(regular)))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold)))
    registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold")
    return "DejaVuSans", "DejaVuSans-Bold"


FONT, FONT_BOLD = _register_fonts()

_base = getSampleStyleSheet()["Normal"]


def _style(name: str, **kw: Any) -> ParagraphStyle:
    kw.setdefault("fontName", FONT)
    kw.setdefault("textColor", TEXT)
    return ParagraphStyle(name, parent=_base, **kw)


STYLES = {
    "brand": _style("rh-brand", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=PRIMARY),
    "title": _style("rh-title", fontName=FONT_BOLD, fontSize=24, leading=29),
    "subtitle": _style("rh-sub", fontSize=9.5, leading=13, textColor=MUTED),
    "heading": _style(
        "rh-h2", fontName=FONT_BOLD, fontSize=13, leading=16, spaceBefore=16, spaceAfter=2
    ),
    "body": _style("rh-body", fontSize=10.5, leading=15.5),
    "figure": _style("rh-figure", fontName=FONT_BOLD, fontSize=22, leading=26),
    "figure_label": _style("rh-figure-l", fontSize=8, leading=10, textColor=MUTED),
    "label": _style("rh-label", fontSize=9, leading=12, textColor=MUTED),
    "value": _style("rh-value", fontSize=9.5, leading=13),
    "cell": _style("rh-cell", fontSize=9, leading=12),
    "cell_bold": _style("rh-cell-b", fontName=FONT_BOLD, fontSize=9, leading=12),
    "cell_indent": _style("rh-cell-i", fontSize=9, leading=12, leftIndent=12),
    "cell_right": _style("rh-cell-r", fontSize=9, leading=12, alignment=TA_RIGHT),
    "head": _style("rh-head", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=MUTED),
    "head_right": _style(
        "rh-head-r", fontName=FONT_BOLD, fontSize=8, leading=10, textColor=MUTED, alignment=TA_RIGHT
    ),
    "small": _style("rh-small", fontSize=8, leading=11, textColor=MUTED),
    "callout_label": _style("rh-call-l", fontName=FONT_BOLD, fontSize=8, leading=10),
    "callout": _style("rh-call", fontName=FONT_BOLD, fontSize=14, leading=18),
}

# The score columns that close the requirements table, at fixed widths so a registered
# section's table can line up with it on page 1. Mixed shows under the all/worst rules,
# Change with a comparison.
SCORE_WIDTHS = {
    "tests": 0.1,
    "failed": 0.1,
    "mixed": 0.09,
    "pass_rate": 0.12,
    "change": 0.1,
    "bar": 0.13,
}


def score_columns(rule: str, compared: bool) -> List[str]:
    keys = ["tests", "failed"]
    if rule != "latest":
        keys.append("mixed")
    keys.append("pass_rate")
    if compared:
        keys.append("change")
    return [*keys, "bar"]


# Longest text a table cell or list line prints; longer text is cut with "…".
CELL_CHARS = 300
LINE_CHARS = 1000

# A4 minus 15 mm margins, minus the frame's own 6 pt padding on each side.
CONTENT_WIDTH = 180 * mm - 12


def shorten(value: Optional[str], limit: int = 100) -> str:
    """One line of *value*, cut at a word before *limit* characters."""
    flat = " ".join((value or "").split())
    if len(flat) <= limit:
        return flat
    return flat[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def text(value: Any) -> str:
    """Escape user text for a Paragraph."""
    return escape("" if value is None else str(value))


def heading(title: str, note: Optional[str] = None) -> List[Any]:
    """A section title with a thin rule under it, and an optional one-line note."""
    out: List[Any] = [
        Paragraph(text(title), STYLES["heading"]),
        HRFlowable(width="100%", thickness=0.6, color=BORDER, spaceBefore=3, spaceAfter=6),
    ]
    if note:
        out += [Paragraph(text(note), STYLES["small"]), Spacer(1, 4)]
    # Never leave a heading alone at the bottom of a page.
    for flowable in out:
        flowable.keepWithNext = True
    return out


def prose(value: Optional[str], empty: str) -> List[Any]:
    """Paragraphs of written text; blank lines split paragraphs."""
    if not value or not value.strip():
        return [Paragraph(f"<i>{text(empty)}</i>", STYLES["label"])]
    return [
        Paragraph(text(part).replace("\n", "<br/>"), STYLES["body"])
        for part in value.strip().split("\n\n")
    ]


def figures(items: Sequence[Tuple[str, str]]) -> Table:
    """Key figures as large numbers with a small caption, divided by thin rules."""
    row = [
        [Paragraph(text(value), STYLES["figure"]), Paragraph(text(label), STYLES["figure_label"])]
        for label, value in items
    ]
    table = Table([row], colWidths=[CONTENT_WIDTH / len(items)] * len(items))
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBEFORE", (1, 0), (-1, -1), 0.6, BORDER),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("LEFTPADDING", (1, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def callout(label: str, value: str, tone: str = "neutral") -> Table:
    """A verdict with a coloured bar on its left: tone is good, warn, bad or neutral."""
    color = {"good": GOOD, "warn": WARN, "bad": FAIL}.get(tone, PRIMARY)
    label_style = ParagraphStyle("rh-call-l-t", parent=STYLES["callout_label"], textColor=color)
    table = Table(
        [
            [
                [
                    Paragraph(text(label).upper(), label_style),
                    Paragraph(text(value), STYLES["callout"]),
                ]
            ]
        ],
        colWidths=[CONTENT_WIDTH],
    )
    table.setStyle(
        TableStyle(
            [
                ("LINEBEFORE", (0, 0), (0, -1), 3, color),
                ("BACKGROUND", (0, 0), (-1, -1), TRACK),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return table


def fields(pairs: Sequence[Tuple[str, str]], columns: int = 1) -> Table:
    """A quiet label/value list: muted label on the left, value on the right.
    ``columns`` > 1 puts pairs side by side."""
    cells = [
        [Paragraph(text(label), STYLES["label"]), Paragraph(text(value), STYLES["value"])]
        for label, value in pairs
    ]
    rows = []
    for i in range(0, len(cells), columns):
        chunk = cells[i : i + columns]
        chunk += [["", ""]] * (columns - len(chunk))
        rows.append([c for pair in chunk for c in pair])
    pair_width = CONTENT_WIDTH / columns
    widths = [pair_width * 0.38, pair_width * 0.62] * columns
    table = Table(rows, colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, BORDER),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def rate_bar(rate: Optional[float], width: float = 18 * mm, height: float = 3.2) -> Drawing:
    """A small pass-rate bar; empty track when nothing was judged."""
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=TRACK, strokeColor=None))
    if rate is not None and rate > 0:
        color = GOOD if rate >= 90 else WARN if rate >= 70 else FAIL
        drawing.add(
            Rect(0, 0, width * min(rate, 100) / 100, height, fillColor=color, strokeColor=None)
        )
    return drawing


def data_table(
    header: Sequence[str],
    rows: Sequence[Sequence[Any]],
    widths: Sequence[float],
    right: Sequence[int] = (),
    bold_rows: Sequence[int] = (),
    fail_cells: Sequence[Tuple[int, int]] = (),
    indent_rows: Sequence[int] = (),
    subtitles: Optional[Dict[int, str]] = None,
) -> Table:
    """A ruled table. ``widths`` are fractions of the content width; ``right`` lists
    right-aligned column indexes; ``fail_cells`` are (row, col) shown in red. A cell
    may hold a flowable (e.g. ``rate_bar``) instead of text. ``subtitles`` puts a small
    muted second line under the first cell of those rows."""
    fail = set(fail_cells)
    subtitles = subtitles or {}

    def cell(value: Any, row: int, col: int) -> Any:
        if isinstance(value, (Flowable, Drawing)):
            return value
        style = STYLES["cell_right"] if col in right else STYLES["cell"]
        if row in bold_rows and col == 0:
            style = STYLES["cell_bold"]
        elif row in indent_rows and col == 0:
            style = STYLES["cell_indent"]
        # A cell taller than a page can't be laid out; no table needs more than this.
        content = text(shorten(str(value), CELL_CHARS) if isinstance(value, str) else value)
        if (row, col) in fail:
            content = f'<font color="{FAIL_HEX}">{content}</font>'
        if col == 0 and subtitles.get(row):
            sub = text(subtitles[row])
            content += f'<br/><font name="{FONT}" size="7.5" color="{MUTED_HEX}">{sub}</font>'
        return Paragraph(content, style)

    head = [
        Paragraph(text(h).upper(), STYLES["head_right"] if i in right else STYLES["head"])
        for i, h in enumerate(header)
    ]
    body = [[cell(v, r, c) for c, v in enumerate(row)] for r, row in enumerate(rows)]
    table = Table([head, *body], colWidths=[w * CONTENT_WIDTH for w in widths], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, TEXT),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def bullets(lines: Sequence[str]) -> Table:
    """A short list of plain-text points."""
    table = Table(
        [
            [
                Paragraph("•", STYLES["value"]),
                Paragraph(text(shorten(line, LINE_CHARS)), STYLES["value"]),
            ]
            for line in lines
        ],
        colWidths=[10, CONTENT_WIDTH - 10],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def keep(flowables: List[Any]) -> KeepTogether:
    return KeepTogether(flowables)


def pass_rate_text(rate: Optional[float]) -> str:
    return "—" if rate is None else f"{rate:.1f}%"
