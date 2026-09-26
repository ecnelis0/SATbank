"""Rendering a `PeriodReport` as a PDF.

reportlab rather than the WeasyPrint the project notes name: WeasyPrint draws
through Pango and Cairo, which are system libraries rather than wheels, so it
cannot render on a machine without them and would turn "download my report" into
an install guide. reportlab is pure Python, ships wheels for every platform, and
is a hard dependency of nothing else here — the trade is hand-built layout
instead of CSS, which for a report of stacked tables is a small price.

The palette is the app's 青绿山水 scroll, so a printed report and the screen it
came from are recognisably the same product.
"""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .report import PeriodReport

# The pigments, straight off the scroll.
SILK = colors.HexColor("#F2F0DC")
SILK_LIT = colors.HexColor("#FAF8EA")
INK = colors.HexColor("#1B2A20")
STONE = colors.HexColor("#4E5A4A")
MALACHITE = colors.HexColor("#6FA061")
MALACHITE_DEEP = colors.HexColor("#3F6B45")
AZURITE = colors.HexColor("#1C5A52")
PEAK = colors.HexColor("#DCE7B8")
OCHRE = colors.HexColor("#6E4A1C")
SEAL = colors.HexColor("#A32E22")
RULE = colors.HexColor("#CFCDAF")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle(
        "body",
        fontName="Times-Roman",
        fontSize=9.5,
        leading=13,
        textColor=INK,
        alignment=TA_LEFT,
    )
    return {
        "title": ParagraphStyle(
            "title", parent=base, fontName="Times-Bold", fontSize=23, leading=26
        ),
        "subtitle": ParagraphStyle("subtitle", parent=base, fontSize=10.5, textColor=STONE),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=MALACHITE_DEEP,
            spaceBefore=2,
            spaceAfter=5,
            # A heading stranded at the foot of a page with its table overleaf
            # reads as an empty section. Drag it forward with its content.
            keepWithNext=1,
        ),
        "body": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=10.5, textColor=STONE),
        "focus": ParagraphStyle("focus", parent=base, fontSize=10, leading=14, leftIndent=9),
        "q": ParagraphStyle("q", parent=base, fontSize=9, leading=12),
    }


class Seal(Flowable):
    """The cinnabar seal, carved rather than printed: the glyph is the silk showing
    through, which is what a 白文 seal looks like."""

    def __init__(self, glyph: str = "M", size: float = 13 * mm) -> None:
        super().__init__()
        self.glyph = glyph
        self.size = size
        self.width = self.height = size

    def draw(self) -> None:
        c = self.canv
        c.setFillColor(SEAL)
        c.roundRect(0, 0, self.size, self.size, 1.2 * mm, stroke=0, fill=1)
        c.setFillColor(SILK)
        c.setFont("Times-Bold", self.size * 0.52)
        c.drawCentredString(self.size / 2, self.size * 0.31, self.glyph)


class Rule(Flowable):
    """A brushed ink rule that thins to nothing, as on every page of the app."""

    def __init__(self, width: float, colour: colors.Color = RULE) -> None:
        super().__init__()
        self.width = width
        self.height = 1.6
        self.colour = colour

    def draw(self) -> None:
        c = self.canv
        for i in range(60):
            c.setStrokeColor(self.colour, alpha=max(0.0, 0.85 * (1 - i / 60)))
            c.setLineWidth(0.9)
            x = self.width * i / 60
            c.line(x, 0, x + self.width / 60 + 0.5, 0)


def _ridges(canvas, doc) -> None:
    """The range across the foot of every page. Flat mineral masses with an ink
    contour — the same recession by hue the app uses, so the sheet reads as a
    piece of the scroll rather than a printout with a logo on it."""
    canvas.saveState()
    canvas.setFillColor(SILK)
    canvas.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    # (pigment, alpha, height, alternating x/y fractions of the silhouette)
    far = (0.0, 0.62, 0.16, 0.30, 0.34, 0.50, 0.55, 0.26, 0.78, 0.58, 1.0, 0.40)
    mid = (0.0, 0.45, 0.20, 0.16, 0.42, 0.40, 0.62, 0.12, 0.84, 0.44, 1.0, 0.22)
    near = (0.0, 0.50, 0.24, 0.20, 0.50, 0.46, 0.74, 0.18, 1.0, 0.42)
    ranges = (
        (PEAK, 0.55, 30 * mm, far),
        (MALACHITE, 0.40, 20 * mm, mid),
        (AZURITE, 0.30, 11 * mm, near),
    )
    for fill, alpha, height, peaks in ranges:
        path = canvas.beginPath()
        path.moveTo(0, 0)
        pairs = list(zip(peaks[::2], peaks[1::2], strict=False))
        for fx, fy in pairs:
            path.lineTo(fx * PAGE_W, fy * height)
        path.lineTo(PAGE_W, 0)
        path.close()
        canvas.setFillColor(fill, alpha=alpha)
        canvas.drawPath(path, stroke=0, fill=1)

    canvas.setFillColor(STONE)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawRightString(PAGE_W - MARGIN, 11 * mm, f"Mistake Bank · page {doc.page}")
    canvas.restoreState()


def _stat_row(report: PeriodReport, styles) -> Table:
    cells = [
        (str(report.logged_count), "logged"),
        (str(report.reviews_answered), "reviews answered"),
        (str(report.reviews_correct), "answered right"),
        (str(report.still_due), "due now"),
        (str(report.untagged_in_window), "with no concept"),
    ]
    big = ParagraphStyle(
        "big", fontName="Times-Bold", fontSize=19, leading=21, textColor=AZURITE
    )
    table = Table(
        [
            [Paragraph(value, big) for value, _ in cells],
            [Paragraph(label, styles["small"]) for _, label in cells],
        ],
        colWidths=[(PAGE_W - 2 * MARGIN) / len(cells)] * len(cells),
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _breakdown(title: str, lines, styles, width: float, show_blurb: bool = False):
    if not lines:
        return []
    rows = []
    for line in lines:
        note = ""
        if show_blurb and line.blurb:
            note = f"<br/><font size=8 color='#4E5A4A'>{_esc(line.blurb)}</font>"
        label = Paragraph(f"<b>{_esc(line.label)}</b>{note}", styles["body"])
        rows.append([label, Paragraph(str(line.count), styles["body"])])
    table = Table(rows, colWidths=[width - 18 * mm, 18 * mm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TEXTCOLOR", (1, 0), (1, -1), MALACHITE_DEEP),
                ("FONTNAME", (1, 0), (1, -1), "Times-Bold"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return [Paragraph(title, styles["h2"]), table, Spacer(1, 7 * mm)]


def _esc(value: str | None) -> str:
    """reportlab's paragraphs are mini-HTML, so a stray & or < in a student's own
    question text would otherwise abort the render."""
    if not value:
        return ""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _question_block(index: int, q, styles, width: float):
    meta = " · ".join(
        part
        for part in (
            f"{q.logged_at:%-d %b %Y}",
            q.section_label,
            q.error_type_label,
            q.urgency_label,
            q.topic,
        )
        if part
    )
    text = q.question_text if len(q.question_text) <= 420 else q.question_text[:417] + "…"
    bits = [
        Paragraph(f"<font color='#6E4A1C'>{index}.</font>  {_esc(meta)}", styles["small"]),
        Spacer(1, 1.5 * mm),
        Paragraph(_esc(text), styles["q"]),
        Spacer(1, 1.5 * mm),
        Paragraph(
            f"You put <b><font color='#A32E22'>{_esc(q.your_answer)}</font></b>"
            f" · answer <b><font color='#1C5A52'>{_esc(q.correct_answer)}</font></b>"
            + (f" · {_esc(', '.join(q.concepts))}" if q.concepts else ""),
            styles["small"],
        ),
    ]
    if q.student_note:
        bits += [
            Spacer(1, 1.2 * mm),
            Paragraph(f"<i>What happened:</i> {_esc(q.student_note)}", styles["small"]),
        ]
    if q.takeaway:
        bits += [
            Spacer(1, 1.2 * mm),
            Paragraph(f"<i>Takeaway:</i> {_esc(q.takeaway)}", styles["small"]),
        ]
    bits.append(Spacer(1, 4 * mm))
    # Kept together so a question never breaks across a page mid-answer.
    return KeepTogether(bits)


def render_pdf(report: PeriodReport, title: str = "Mistake Bank report") -> bytes:
    styles = _styles()
    buffer = io.BytesIO()
    width = PAGE_W - 2 * MARGIN

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN + 12 * mm,
        title=title,
        author="Mistake Bank",
    )
    doc.addPageTemplates(
        [
            PageTemplate(
                id="scroll",
                frames=[
                    Frame(
                        MARGIN,
                        MARGIN + 12 * mm,
                        width,
                        PAGE_H - 2 * MARGIN - 12 * mm,
                        leftPadding=0,
                        rightPadding=0,
                        topPadding=0,
                        bottomPadding=0,
                    )
                ],
                onPage=_ridges,
            )
        ]
    )

    story: list = []

    header = Table(
        [[Seal(title.strip()[:1].upper() or "M"), Paragraph(_esc(title), styles["title"])]],
        colWidths=[17 * mm, width - 17 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story += [
        header,
        Spacer(1, 2 * mm),
        Paragraph(
            f"{_esc(report.window_label)} · generated {report.generated_at:%-d %b %Y, %H:%M} UTC",
            styles["subtitle"],
        ),
        Spacer(1, 3 * mm),
        Rule(width),
        Spacer(1, 6 * mm),
        _stat_row(report, styles),
        Spacer(1, 8 * mm),
    ]

    # The conclusion goes first. A report you have to read to the end to find out
    # what to do with is a report nobody acts on.
    story.append(Paragraph("WHAT TO WORK ON", styles["h2"]))
    for item in report.focus:
        story.append(Paragraph(f"•  {_esc(item)}", styles["focus"]))
        story.append(Spacer(1, 2 * mm))
    story.append(Spacer(1, 6 * mm))

    story += _breakdown("WHY YOU LOST POINTS", report.by_error_type, styles, width, True)
    story += _breakdown("BY TOPIC", report.by_topic, styles, width)
    story += _breakdown("BY SECTION", report.by_section, styles, width)
    story += _breakdown("BY URGENCY", report.by_urgency, styles, width)

    touched = [c for c in report.concepts if c.questions_in_window]
    if touched:
        rows = [
            [
                Paragraph(
                    f"<b>{_esc(c.title)}</b><br/><font size=8 color='#4E5A4A'>"
                    f"written {c.created_at:%-d %b %Y}</font>",
                    styles["body"],
                ),
                Paragraph(f"{c.questions_in_window} of {c.questions_total}", styles["body"]),
            ]
            for c in touched
        ]
        table = Table(rows, colWidths=[width - 30 * mm, 30 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("TEXTCOLOR", (1, 0), (1, -1), MALACHITE_DEEP),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story += [Paragraph("CONCEPTS THIS TOUCHED", styles["h2"]), table, Spacer(1, 7 * mm)]

    heading = Paragraph("EVERY QUESTION IN THIS WINDOW", styles["h2"])
    if not report.questions:
        story.append(
            KeepTogether([heading, Paragraph("Nothing was logged in this window.", styles["body"])])
        )
    else:
        blocks = [
            _question_block(index, question, styles, width)
            for index, question in enumerate(report.questions, start=1)
        ]
        # `keepWithNext` is not enough on its own here: when the first question is
        # taller than the space left, reportlab strands the heading and moves only
        # the question. Binding the two into one flowable moves them together.
        story.append(KeepTogether([heading, blocks[0]]))
        story.extend(blocks[1:])

    doc.build(story)
    return buffer.getvalue()
