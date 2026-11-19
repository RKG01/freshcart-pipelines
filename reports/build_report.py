"""Render assignment_report.md as a compact PDF without modifying its evidence."""

from __future__ import annotations

import html
import re
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    BaseDocTemplate,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from PIL import Image as PILImage

REPORT_PATH = Path(__file__).with_name("assignment_report.md")
PDF_PATH = REPORT_PATH.with_name("23BCS074_Devansh_Singh_Pipelines.pdf")
BONUS_EVIDENCE_DIR = REPORT_PATH.parent / "bonus" / "live_5f057039be864ea497eaa9496e2810bd"


class ArchitectureDiagram(Flowable):
    """Draw a compact conceptual diagram for the report."""

    def __init__(self, width: float):
        super().__init__()
        self.width = width
        self.height = 92

    def draw(self):
        canvas = self.canv
        top_nodes = ["Git", "CI / pytest", "FreshCart ELT", "Snowflake gold", "Mage ML"]
        box_width = 76
        gap = (self.width - box_width * len(top_nodes)) / (len(top_nodes) - 1)
        top_y = 58

        def draw_box(x, y, label):
            canvas.setStrokeColor(colors.HexColor("#35566F"))
            canvas.setFillColor(colors.HexColor("#EDF3F7"))
            canvas.roundRect(x, y, box_width, 24, 3, stroke=1, fill=1)
            canvas.setFillColor(colors.HexColor("#182B3A"))
            canvas.setFont("Helvetica", 7.5)
            canvas.drawCentredString(x + box_width / 2, y + 9, label)

        def draw_arrow(x1, y1, x2, y2):
            canvas.setStrokeColor(colors.HexColor("#526B7C"))
            canvas.line(x1, y1, x2, y2)
            canvas.line(x2, y2, x2 - 4, y2 + 3)
            canvas.line(x2, y2, x2 - 4, y2 - 3)

        for index, label in enumerate(top_nodes):
            x = index * (box_width + gap)
            draw_box(x, top_y, label)
            if index < len(top_nodes) - 1:
                draw_arrow(x + box_width + 2, top_y + 12, x + box_width + gap - 3, top_y + 12)

        rabbit_x = self.width * 0.30
        driver_x = self.width * 0.64
        draw_box(rabbit_x, 8, "RabbitMQ events")
        draw_box(driver_x, 8, "Driver queues")
        draw_arrow(rabbit_x + box_width + 3, 20, driver_x - 4, 20)
        draw_arrow(rabbit_x + box_width / 2, 34, rabbit_x + box_width / 2, 56)
        canvas.setFont("Helvetica-Oblique", 6.5)
        canvas.setFillColor(colors.HexColor("#526B7C"))
        canvas.drawString(rabbit_x + box_width + 8, 24, "routes")


def _inline(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return escaped


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append([_inline(cell) for cell in cells])
    return rows


def build_pdf() -> Path:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#203F56"), fontSize=20, leading=24, spaceAfter=12))
    styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading1"], textColor=colors.HexColor("#203F56"), fontSize=14, leading=16.5, spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="SubHeading", parent=styles["Heading2"], textColor=colors.HexColor("#365F78"), fontSize=10.5, leading=12.5, spaceBefore=6, spaceAfter=3))
    styles.add(ParagraphStyle(name="BodyCompact", parent=styles["BodyText"], fontSize=8.1, leading=10.4, spaceAfter=4))
    styles.add(ParagraphStyle(name="BulletCompact", parent=styles["BodyCompact"], leftIndent=12, firstLineIndent=-8))
    styles.add(ParagraphStyle(name="TableText", parent=styles["BodyCompact"], fontSize=7.1, leading=9, spaceAfter=0))
    styles.add(ParagraphStyle(name="TableHeader", parent=styles["TableText"], textColor=colors.white, fontName="Helvetica-Bold"))

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#667780"))
        canvas.drawString(16 * mm, 9 * mm, "From Git to Gold | Devansh Singh | 23BCS074")
        canvas.drawRightString(doc.pagesize[0] - 16 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()

    portrait_size = A4
    landscape_size = landscape(A4)
    portrait_frame = Frame(
        16 * mm, 16 * mm, portrait_size[0] - 32 * mm, portrait_size[1] - 31 * mm,
        id="portrait_frame",
    )
    landscape_frame = Frame(
        16 * mm, 16 * mm, landscape_size[0] - 32 * mm, landscape_size[1] - 31 * mm,
        id="landscape_frame",
    )
    document = BaseDocTemplate(
        str(PDF_PATH),
        pagesize=portrait_size,
        title="From Git to Gold - Data Engineering Assignment",
        author="Devansh Singh",
    )
    document.width = portrait_size[0] - 32 * mm
    document.addPageTemplates([
        PageTemplate("Portrait", frames=[portrait_frame], pagesize=portrait_size, onPage=draw_footer),
        PageTemplate("AppendixLandscape", frames=[landscape_frame], pagesize=landscape_size, onPage=draw_footer),
    ])
    story = []
    appendix_images = []
    lines = REPORT_PATH.read_text(encoding="utf-8").splitlines()
    index = 0
    code_lines = []
    in_code = False
    code_language = ""

    while index < len(lines):
        line = lines[index]
        if line.startswith("## Appendix: screenshot evidence"):
            for appendix_line in lines[index + 1:]:
                image_match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", appendix_line)
                if image_match:
                    image_path = (REPORT_PATH.parent / image_match.group(2)).resolve()
                    if image_path.is_file():
                        appendix_images.append((image_match.group(1), image_path))
            break
        if line.startswith("```"):
            if not in_code:
                in_code = True
                code_language = line[3:].strip()
                code_lines = []
            else:
                in_code = False
                if code_language == "mermaid":
                    story.append(ArchitectureDiagram(document.width))
                else:
                    story.append(Preformatted("\n".join(code_lines), ParagraphStyle("Code", fontName="Courier", fontSize=6.7, leading=8.4, backColor=colors.HexColor("#F3F5F6"), borderPadding=5), maxLineLength=120))
                story.append(Spacer(1, 4))
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        image_match = re.fullmatch(r"!\[(.*?)\]\((.*?)\)", line)
        if image_match:
            image_path = (REPORT_PATH.parent / image_match.group(2)).resolve()
            if image_path.is_file():
                appendix_images.append((image_match.group(1), image_path))
            index += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            rows = _table_rows(table_lines)
            if rows:
                formatted = []
                for row_index, row in enumerate(rows):
                    style = styles["TableHeader"] if row_index == 0 else styles["TableText"]
                    formatted.append([Paragraph(cell, style) for cell in row])
                columns = max(len(row) for row in formatted)
                table = Table(formatted, colWidths=[document.width / columns] * columns, repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#35566F")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C3CA")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.extend([table, Spacer(1, 5)])
            continue
        if line.startswith("# "):
            story.append(Paragraph(_inline(line[2:]), styles["ReportTitle"]))
        elif line.startswith("## "):
            story.append(Paragraph(_inline(line[3:]), styles["SectionHeading"]))
        elif line.startswith("#### "):
            story.append(Paragraph(_inline(line[5:]), styles["SubHeading"]))
        elif line.startswith("### "):
            story.append(Paragraph(_inline(line[4:]), styles["SubHeading"]))
        elif line.startswith("- "):
            story.append(Paragraph("&#8226; " + _inline(line[2:]), styles["BulletCompact"]))
        elif re.match(r"\d+\. ", line):
            story.append(Paragraph(_inline(line), styles["BulletCompact"]))
        elif line.strip() == "---":
            story.append(Spacer(1, 4))
        elif line.strip():
            story.append(Paragraph(_inline(line), styles["BodyCompact"]))
        index += 1

    if appendix_images:
        story.append(NextPageTemplate("Portrait"))
        story.append(PageBreak())
        for image_index, (caption, image_path) in enumerate(appendix_images):
            with PILImage.open(image_path) as screenshot:
                image_width, image_height = screenshot.size
            template = "AppendixLandscape" if image_width / image_height > 1.55 else "Portrait"
            if image_index > 0:
                story.append(NextPageTemplate(template))
                story.append(PageBreak())
            if template == "AppendixLandscape":
                image_box = (landscape_size[0] - 32 * mm, landscape_size[1] - 50 * mm)
            else:
                image_box = (portrait_size[0] - 32 * mm, 220 * mm)
            image = Image(str(image_path), width=image_box[0], height=image_box[1], kind="bound")
            group = (
                "GitHub Actions (3 screenshots)" if image_index < 3 else
                "Mage (3 screenshots)" if image_index < 6 else
                "RabbitMQ management UI (2 screenshots)" if image_index < 8 else
                "Snowflake saved-record evidence (4 screenshots; not live Snowsight captures)"
            )
            contents = []
            if image_index == 0:
                contents.append(Paragraph("Screenshot Appendix", styles["SectionHeading"]))
            if image_index in (0, 3, 6, 8):
                contents.append(Paragraph(group, styles["SubHeading"]))
            contents.extend([Paragraph(_inline(caption), styles["BodyCompact"]), image])
            story.append(KeepTogether(contents))

    if BONUS_EVIDENCE_DIR.is_dir():
        story.append(PageBreak())
        story.append(Paragraph("Appendix: live RabbitMQ-to-Snowflake bonus evidence", styles["SectionHeading"]))
        story.append(Paragraph(
            "The following excerpts are rendered from the genuine saved process logs and SQL snapshots in "
            "reports/bonus/live_5f057039be864ea497eaa9496e2810bd/. They are captured execution evidence, "
            "not screenshots of the Snowflake UI. The run used FRESHCART_BONUS only.",
            styles["BodyCompact"],
        ))
        story.append(Paragraph(
            "One publisher invocation confirmed two messages. The consumer collection lasted 60.001 seconds. "
            "Replay loaded the same two business payloads from the original landing file into a new physical file. "
            "Five physical landing files were created: the initial web, CRM, FX, and pincode files, plus the replay web file. "
            "The FX fixture contains three rates. A local payload comparison confirmed the business records match "
            "(payload_comparison.log).",
            styles["BodyCompact"],
        ))
        bonus_rows = [
            ["Metric", "First pass", "After replay"],
            ["Bronze order rows", "2", "4"],
            ["Silver deduplicated orders", "2", "2"],
            ["Gold orders", "2", "2"],
            ["Gold revenue", "INR 5,092.38", "INR 5,092.38"],
            ["Gold loyalty points", "50", "50"],
            ["Duplicate Gold order IDs", "0", "0"],
        ]
        formatted_bonus_rows = []
        for row_index, row in enumerate(bonus_rows):
            style = styles["TableHeader"] if row_index == 0 else styles["TableText"]
            formatted_bonus_rows.append([Paragraph(_inline(cell), style) for cell in row])
        bonus_table = Table(formatted_bonus_rows, colWidths=[document.width * 0.47, document.width * 0.265, document.width * 0.265], repeatRows=1)
        bonus_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#35566F")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7C3CA")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.extend([bonus_table, Spacer(1, 6)])
        story.append(Paragraph(
            "BONUS-ORDER-001: INR 1,550.00 and 15 points. BONUS-ORDER-002: INR 3,542.38 and 35 points. "
            "The consumer's OS exit code was not captured; its complete log records successful processing stages and final results. "
            "The publisher and replay exit codes were 0.",
            styles["BodyCompact"],
        ))

        def append_evidence_excerpt(title: str, filename: str, predicate, *, new_page: bool = False):
            path = BONUS_EVIDENCE_DIR / filename
            if not path.is_file():
                return
            source_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            selected = [line for line in source_lines if predicate(line)]
            if not selected:
                return
            if new_page:
                story.append(PageBreak())
            wrapped = "\n".join(part for line in selected for part in textwrap.wrap(line, width=100, break_long_words=True, break_on_hyphens=False) or [""])
            excerpt = Preformatted(wrapped, ParagraphStyle("BonusEvidenceCode", fontName="Courier", fontSize=7.3, leading=9, backColor=colors.HexColor("#F3F5F6"), borderPadding=5))
            story.extend([Paragraph(title, styles["SubHeading"]), Paragraph(f"Source: reports/bonus/live_5f057039be864ea497eaa9496e2810bd/{filename}", styles["BodyCompact"]), excerpt])

        append_evidence_excerpt("Publisher confirmations", "bonus_publisher.log", lambda line: line.startswith("PUBLISHED "))
        append_evidence_excerpt("Consumer execution output", "bonus_consumer.log", lambda line: line.startswith(("BATCH_ID=", "ACKED ", "TRANSFORM_STAGE=", "DUPLICATE_GOLD_ORDER_IDS=", "SNOWFLAKE_DATABASE=", "BRONZE_ORDERS=", "GOLD=", "GOLD_ORDER_IDS=")), new_page=True)
        append_evidence_excerpt("Replay execution output", "bonus_replay.log", lambda line: line.startswith(("REPLAY_SOURCE=", "TRANSFORM_STAGE=", "DUPLICATE_GOLD_ORDER_IDS=", "SNOWFLAKE_DATABASE=", "BRONZE_ORDERS=", "GOLD=", "GOLD_ORDER_IDS=")))
        append_evidence_excerpt("Actual SQL snapshot results", "first_snapshot.log", lambda line: line.startswith(("DATABASE=", "RESULT_", "FIRST_PASS_SNAPSHOT=")), new_page=True)
        append_evidence_excerpt("Actual SQL snapshot results after replay", "replay_snapshot.log", lambda line: line.startswith(("DATABASE=", "RESULT_", "REPLAY_SNAPSHOT=")))

    document.build(story)
    return PDF_PATH


if __name__ == "__main__":
    print(build_pdf())
