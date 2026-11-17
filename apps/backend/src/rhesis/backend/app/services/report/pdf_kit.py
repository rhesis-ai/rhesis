"""The building blocks of a report PDF, shared by core and EE sections so they print alike."""

from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

PRIMARY = colors.HexColor("#0080af")
TEXT = colors.HexColor("#16232c")
MUTED = colors.HexColor("#5a6b77")
BORDER = colors.HexColor("#dbe3e9")
FIELD = colors.HexColor("#f4f7f9")
FAIL_HEX = "#b52a47"
FAIL = colors.HexColor(FAIL_HEX)

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

_base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle(
        "rh-title",
        parent=_base["Title"],
        fontName=FONT_BOLD,
        alignment=0,
        fontSize=20,
        leading=24,
        textColor=TEXT,
    ),
    "subtitle": ParagraphStyle(
        "rh-sub", parent=_base["Normal"], fontName=FONT, fontSize=9, textColor=MUTED
    ),
    "heading": ParagraphStyle(
        "rh-h2",
        parent=_base["Heading2"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=PRIMARY,
        spaceBefore=12,
        spaceAfter=6,
    ),
    "body": ParagraphStyle(
        "rh-body", parent=_base["Normal"], fontName=FONT, fontSize=10, leading=14
    ),
    "label": ParagraphStyle(
        "rh-label", parent=_base["Normal"], fontName=FONT, fontSize=8, textColor=MUTED
    ),
    "cell": ParagraphStyle(
        "rh-cell", parent=_base["Normal"], fontName=FONT, fontSize=9, leading=12
    ),
    "cell_bold": ParagraphStyle(
        "rh-cell-b", parent=_base["Normal"], fontSize=9, leading=12, fontName=FONT_BOLD
    ),
    "cell_indent": ParagraphStyle(
        "rh-cell-i", parent=_base["Normal"], fontName=FONT, fontSize=9, leading=12, leftIndent=12
    ),
    "cell_right": ParagraphStyle(
        "rh-cell-r",
        parent=_base["Normal"],
        fontName=FONT,
        fontSize=9,
        leading=12,
        alignment=TA_RIGHT,
    ),
    "small": ParagraphStyle(
        "rh-small", parent=_base["Normal"], fontName=FONT, fontSize=8, textColor=MUTED
    ),
}

CONTENT_WIDTH = 180 * mm  # A4 minus margins


def text(value: Any) -> str:
    """Escape user text for a Paragraph."""
    return escape("" if value is None else str(value))


def heading(title: str, note: Optional[str] = None) -> List[Any]:
    out: List[Any] = [Paragraph(text(title), STYLES["heading"])]
    if note:
        out.append(Paragraph(text(note), STYLES["small"]))
        out.append(Spacer(1, 4))
    return out


def fields(pairs: Sequence[Tuple[str, str]], columns: int = 1) -> Table:
    """Label over value, in a grid of ``columns``, on the light field background."""
    cells = [
        [Paragraph(text(label), STYLES["label"]), Paragraph(text(value), STYLES["body"])]
        for label, value in pairs
    ]
    rows = [cells[i : i + columns] for i in range(0, len(cells), columns)]
    rows[-1] += [""] * (columns - len(rows[-1]))
    table = Table(rows, colWidths=[CONTENT_WIDTH / columns] * columns)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), FIELD),
                ("INNERGRID", (0, 0), (-1, -1), 4, colors.white),
                ("BOX", (0, 0), (-1, -1), 4, colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def data_table(
    header: Sequence[str],
    rows: Sequence[Sequence[Any]],
    widths: Sequence[float],
    right: Sequence[int] = (),
    bold_rows: Sequence[int] = (),
    fail_cells: Sequence[Tuple[int, int]] = (),
    indent_rows: Sequence[int] = (),
) -> Table:
    """A ruled table. ``widths`` are fractions of the content width; ``right`` lists
    right-aligned column indexes; ``fail_cells`` are (row, col) shown in red."""
    fail = set(fail_cells)

    def cell(value: Any, row: int, col: int) -> Paragraph:
        style = STYLES["cell_right"] if col in right else STYLES["cell"]
        if row in bold_rows and col == 0:
            style = STYLES["cell_bold"]
        elif row in indent_rows and col == 0:
            style = STYLES["cell_indent"]
        content = text(value)
        if (row, col) in fail:
            content = f'<font color="{FAIL_HEX}">{content}</font>'
        return Paragraph(content, style)

    head = [
        Paragraph(f"<b>{text(h)}</b>", STYLES["cell_right"] if i in right else STYLES["cell"])
        for i, h in enumerate(header)
    ]
    body = [[cell(v, r, c) for c, v in enumerate(row)] for r, row in enumerate(rows)]
    table = Table([head, *body], colWidths=[w * CONTENT_WIDTH for w in widths], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, MUTED),
                ("LINEBELOW", (0, 1), (-1, -1), 0.3, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def keep(flowables: List[Any]) -> KeepTogether:
    return KeepTogether(flowables)


def pass_rate_text(rate: Optional[float]) -> str:
    return "—" if rate is None else f"{rate:.1f}%"
