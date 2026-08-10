"""Deterministic PDF rendering for validated persisted chat reports."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from io import BytesIO
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.chat.reports import ChatReportRead, ReportClaim, ReportSection


_INK = colors.HexColor("#171717")
_MUTED = colors.HexColor("#6B6A66")
_RULE = colors.HexColor("#C9C7BF")
_PANEL = colors.HexColor("#F4F3EF")
_ACCENT = colors.HexColor("#365A70")
_PAGE_WIDTH, _PAGE_HEIGHT = A4


def render_chat_report_pdf(
    report: ChatReportRead,
    *,
    thread_title: str,
) -> bytes:
    """Render a completed persisted report without calling the model."""

    if report.report is None:
        raise ValueError("a structured report is required for PDF rendering")

    font_names = _register_fonts()
    styles = _build_styles(font_names)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=_plain(report.report.title),
        author="CyberCase Intelligence Framework",
        subject="Provisional unverified digital-forensics report",
    )

    story = _build_story(report, thread_title=thread_title, styles=styles)
    document.build(
        story,
        onFirstPage=lambda canvas, doc: _draw_page_chrome(
            canvas, doc, font_names=font_names
        ),
        onLaterPages=lambda canvas, doc: _draw_page_chrome(
            canvas, doc, font_names=font_names
        ),
    )
    return buffer.getvalue()


def _build_story(
    report: ChatReportRead,
    *,
    thread_title: str,
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    assert report.report is not None
    structured_report = report.report
    story: list[object] = [
        Paragraph("CYBERCASE INTELLIGENCE FRAMEWORK", styles["eyebrow"]),
        Spacer(1, 8 * mm),
        Paragraph(_paragraph_text(structured_report.title), styles["title"]),
        Spacer(1, 3 * mm),
        Paragraph(
            "PROVISIONAL / UNVERIFIED REPORT",
            styles["status"],
        ),
        Spacer(1, 10 * mm),
        Paragraph(
            "This document is a formal presentation of one validated structured report version. "
            "It contains user-reported and extraction-derived candidates and is not confirmed forensic evidence.",
            styles["lead"],
        ),
        Spacer(1, 8 * mm),
        _metadata_table(report, thread_title=thread_title, styles=styles),
        Spacer(1, 10 * mm),
        HRFlowable(width="100%", thickness=0.8, color=_RULE),
        Spacer(1, 7 * mm),
        Paragraph(
            "Source and handling note",
            styles["subheading"],
        ),
        Paragraph(
            "The report was generated from the frozen server-side chat snapshot identified below. "
            "The PDF renderer does not add facts, references, or conclusions.",
            styles["body"],
        ),
        PageBreak(),
    ]

    for index, section in enumerate(structured_report.sections, start=1):
        story.extend(
            _section_story(
                section,
                claims=[
                    claim
                    for claim in structured_report.claims
                    if claim.section_id == section.section_id
                ],
                index=index,
                styles=styles,
            )
        )

    if structured_report.limitations:
        story.extend(
            [
                Spacer(1, 5 * mm),
                HRFlowable(width="100%", thickness=0.8, color=_RULE),
                Spacer(1, 5 * mm),
                Paragraph("Report limitations", styles["section_heading"]),
            ]
        )
        for limitation in structured_report.limitations:
            story.append(Paragraph(f"- {_paragraph_text(limitation)}", styles["body"]))
            story.append(Spacer(1, 1.5 * mm))

    story.extend(
        [
            Spacer(1, 7 * mm),
            HRFlowable(width="100%", thickness=0.8, color=_RULE),
            Spacer(1, 4 * mm),
            Paragraph(
                "End of report - provisional and unverified",
                styles["end_note"],
            ),
        ]
    )
    return story


def _section_story(
    section: ReportSection,
    *,
    claims: list[ReportClaim],
    index: int,
    styles: dict[str, ParagraphStyle],
) -> list[object]:
    story: list[object] = [
        Spacer(1, 3 * mm),
        Paragraph(
            f"{index:02d}  {_paragraph_text(section.heading)}",
            styles["section_heading"],
        ),
        Spacer(1, 3 * mm),
    ]
    for paragraph in section.paragraphs:
        story.append(Paragraph(_paragraph_text(paragraph), styles["body"]))
        story.append(Spacer(1, 2.5 * mm))
    for item in section.items:
        story.append(Paragraph(f"- {_paragraph_text(item)}", styles["body"]))
        story.append(Spacer(1, 1.5 * mm))

    if claims:
        story.extend(
            [
                Spacer(1, 2 * mm),
                Paragraph("Structured claims", styles["subheading"]),
            ]
        )
        for claim in claims:
            claim_text = (
                f"<b>{_paragraph_text(claim.claim_id)}</b>  "
                f"<font color=\"#365A70\">"
                f"{_paragraph_text(claim.support_type.replace('_', ' '))}</font><br/>"
                f"{_paragraph_text(claim.text)}"
            )
            references = _claim_references(claim)
            if references:
                claim_text += (
                    f"<br/><font color=\"#6B6A66\">"
                    f"References: {_paragraph_text(references)}</font>"
                )
            story.append(
                KeepTogether(
                    [
                        Paragraph(claim_text, styles["claim"]),
                        Spacer(1, 2 * mm),
                    ]
                )
            )
    return story


def _metadata_table(
    report: ChatReportRead,
    *,
    thread_title: str,
    styles: dict[str, ParagraphStyle],
) -> Table:
    rows = [
        ("Case / thread", thread_title),
        (
            "Report version",
            f"Version {report.version_number} / {report.report.report_version}",
        ),
        ("Report ID", str(report.report_id)),
        ("Generated", _format_datetime(report.finished_at or report.created_at)),
        ("Extraction", report.extraction_version),
        ("Validation", report.validation_status),
        ("Provider / model", f"{report.provider} / {report.model}"),
        ("Prompt version", report.prompt_version),
        ("Source snapshot", report.source_snapshot_hash),
    ]
    table = Table(
        [
            [
                Paragraph(_paragraph_text(label), styles["metadata_label"]),
                Paragraph(_paragraph_text(value), styles["metadata_value"]),
            ]
            for label, value in rows
        ],
        colWidths=[38 * mm, 118 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _PANEL),
                ("BOX", (0, 0), (-1, -1), 0.7, _RULE),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DEDCD5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _build_styles(font_names: tuple[str, str]) -> dict[str, ParagraphStyle]:
    regular, bold = font_names
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "ReportEyebrow",
            parent=base["Normal"],
            fontName=bold,
            fontSize=8,
            leading=10,
            textColor=_ACCENT,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName=bold,
            fontSize=23,
            leading=28,
            textColor=_INK,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "status": ParagraphStyle(
            "ReportStatus",
            parent=base["Normal"],
            fontName=bold,
            fontSize=8,
            leading=11,
            textColor=_MUTED,
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "lead": ParagraphStyle(
            "ReportLead",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=10.5,
            leading=16,
            textColor=_MUTED,
            alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9.5,
            leading=14,
            textColor=_INK,
            alignment=TA_LEFT,
            splitLongWords=1,
        ),
        "section_heading": ParagraphStyle(
            "ReportSectionHeading",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=14,
            leading=18,
            textColor=_INK,
            alignment=TA_LEFT,
            spaceBefore=4 * mm,
            spaceAfter=0,
        ),
        "subheading": ParagraphStyle(
            "ReportSubheading",
            parent=base["Heading3"],
            fontName=bold,
            fontSize=9,
            leading=12,
            textColor=_ACCENT,
            alignment=TA_LEFT,
            spaceBefore=2 * mm,
            spaceAfter=2 * mm,
        ),
        "claim": ParagraphStyle(
            "ReportClaim",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8.8,
            leading=13,
            textColor=_INK,
            backColor=colors.HexColor("#FAFAF8"),
            borderColor=colors.HexColor("#DEDCD5"),
            borderWidth=0.5,
            borderPadding=6,
            spaceAfter=0,
        ),
        "metadata_label": ParagraphStyle(
            "ReportMetadataLabel",
            parent=base["Normal"],
            fontName=bold,
            fontSize=7.8,
            leading=10,
            textColor=_MUTED,
        ),
        "metadata_value": ParagraphStyle(
            "ReportMetadataValue",
            parent=base["Normal"],
            fontName=regular,
            fontSize=8.2,
            leading=11,
            textColor=_INK,
        ),
        "end_note": ParagraphStyle(
            "ReportEndNote",
            parent=base["Normal"],
            fontName=bold,
            fontSize=8,
            leading=11,
            textColor=_MUTED,
            alignment=TA_CENTER,
        ),
    }


def _draw_page_chrome(canvas, document, *, font_names: tuple[str, str]) -> None:
    regular, bold = font_names
    canvas.saveState()
    canvas.setStrokeColor(_RULE)
    canvas.setLineWidth(0.6)
    canvas.line(document.leftMargin, _PAGE_HEIGHT - 14 * mm, _PAGE_WIDTH - document.rightMargin, _PAGE_HEIGHT - 14 * mm)
    canvas.line(document.leftMargin, 13 * mm, _PAGE_WIDTH - document.rightMargin, 13 * mm)
    canvas.setFont(bold, 7)
    canvas.setFillColor(_MUTED)
    canvas.drawString(document.leftMargin, _PAGE_HEIGHT - 11 * mm, "CYBERCASE INTELLIGENCE FRAMEWORK")
    canvas.drawRightString(
        _PAGE_WIDTH - document.rightMargin,
        _PAGE_HEIGHT - 11 * mm,
        "PROVISIONAL / UNVERIFIED",
    )
    canvas.setFont(regular, 7)
    canvas.drawString(document.leftMargin, 8 * mm, "Formal report export - validate against the persisted report version")
    canvas.drawRightString(_PAGE_WIDTH - document.rightMargin, 8 * mm, f"Page {document.page}")
    canvas.restoreState()


def _claim_references(claim: ReportClaim) -> str:
    references: list[str] = []
    if claim.evidence_ids:
        references.append(f"evidence {', '.join(claim.evidence_ids)}")
    if claim.timeline_event_ids:
        references.append(f"timeline {', '.join(claim.timeline_event_ids)}")
    if claim.mitre_technique_ids:
        references.append(f"MITRE {', '.join(claim.mitre_technique_ids)}")
    return "; ".join(references)


def _format_datetime(value: datetime) -> str:
    normalized = value
    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)
    return normalized.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _paragraph_text(value: object) -> str:
    text = _plain(value)
    return escape(text).replace("\n", "<br/>")


def _plain(value: object) -> str:
    return (
        str(value)
        .replace("\u2010", "-")
        .replace("\u2011", "-")
        .replace("\u2012", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
    )


def _register_fonts() -> tuple[str, str]:
    regular_path = _find_font(
        "CYBERCASE_PDF_FONT",
        (
            "/usr/share/fonts/truetype/tlwg/Garuda.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ),
    )
    bold_path = _find_font(
        "CYBERCASE_PDF_BOLD_FONT",
        (
            "/usr/share/fonts/truetype/tlwg/Garuda-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansThai-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ),
    )
    if regular_path is None or bold_path is None:
        return "Helvetica", "Helvetica-Bold"

    pdfmetrics.registerFont(TTFont("CyberCaseSans", regular_path))
    pdfmetrics.registerFont(TTFont("CyberCaseSansBold", bold_path))
    return "CyberCaseSans", "CyberCaseSansBold"


def _find_font(environment_name: str, candidates: tuple[str, ...]) -> str | None:
    configured = Path(os.environ.get(environment_name, ""))
    if configured.is_file():
        return str(configured)
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return str(path)
    return None


__all__ = ["render_chat_report_pdf"]
