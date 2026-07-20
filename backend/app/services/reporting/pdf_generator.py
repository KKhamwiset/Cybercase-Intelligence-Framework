from __future__ import annotations

import io
import re
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_pdf_from_markdown(markdown_content: str, title: str = "CyberCase Investigation Report") -> bytes:
    """Parses basic Markdown structure and generates PDF bytes using ReportLab."""
    buffer = io.BytesIO()
    
    # Page Margins: 0.75 in (54 pt)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=15,
    )
    
    h2_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.black,
    )
    
    h3_style = ParagraphStyle(
        "SubSectionHeading",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.black,
    )
    
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        spaceAfter=6,
    )
    
    list_style = ParagraphStyle(
        "ReportList",
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4,
    )
    
    story = []
    
    # Title
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 10))
    
    # Escape XML entities & map markdown inline formatting
    def process_text(text: str) -> str:
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Bold: **text** -> <b>text</b>
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        # Italic: *text* -> <i>text</i>
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
        # Inline Code: `code` -> Courier font
        text = re.sub(r'`(.*?)`', r'<font face="Courier" size="8">\1</font>', text)
        return text
    
    lines = markdown_content.splitlines()
    in_table = False
    table_data = []
    current_para = []
    
    def flush_table():
        if table_data:
            t = Table(table_data, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f3f4f6")),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#d1d5db")),
                ('PADDING', (0,0), (-1,-1), 5),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))
            table_data.clear()
            
    for line in lines:
        stripped = line.strip()
        
        # Check if line belongs to a markdown table
        if stripped.startswith("|") and stripped.endswith("|"):
            if current_para:
                text_block = " ".join(current_para)
                story.append(Paragraph(process_text(text_block), body_style))
                current_para = []
                
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            # Skip delimiter rows (e.g. |---|---|)
            if all(re.match(r'^:?-+:?$', c) for c in cells):
                continue
                
            table_data.append([Paragraph(process_text(c), body_style) for c in cells])
            in_table = True
            continue
        else:
            if in_table:
                flush_table()
                in_table = False
                
        if not stripped:
            if current_para:
                text_block = " ".join(current_para)
                story.append(Paragraph(process_text(text_block), body_style))
                current_para = []
            continue
            
        # Headers
        if stripped.startswith("#"):
            if current_para:
                text_block = " ".join(current_para)
                story.append(Paragraph(process_text(text_block), body_style))
                current_para = []
                
            level = len(line) - len(line.lstrip("#"))
            header_text = line.lstrip("#").strip()
            
            # Skip the main title in markdown since we draw it as document title
            if level == 1 and header_text == "CyberCase Investigation Report":
                continue
                
            if level == 1:
                story.append(Paragraph(process_text(header_text), title_style))
            elif level == 2:
                story.append(Spacer(1, 10))
                story.append(Paragraph(process_text(header_text), h2_style))
            else:
                story.append(Paragraph(process_text(header_text), h3_style))
                
        # Bullet list item
        elif stripped.startswith(("- ", "* ", "• ")):
            if current_para:
                text_block = " ".join(current_para)
                story.append(Paragraph(process_text(text_block), body_style))
                current_para = []
                
            bullet_text = stripped[2:].strip()
            story.append(Paragraph(f"&bull; {process_text(bullet_text)}", list_style))
            
        # Numbered list item
        elif re.match(r'^\d+\.\s', stripped):
            if current_para:
                text_block = " ".join(current_para)
                story.append(Paragraph(process_text(text_block), body_style))
                current_para = []
                
            match = re.match(r'^(\d+\.)\s(.*)', stripped)
            if match:
                prefix = match.group(1)
                bullet_text = match.group(2).strip()
                story.append(Paragraph(f"{prefix} {process_text(bullet_text)}", list_style))
                
        else:
            current_para.append(stripped)
            
    if in_table:
        flush_table()
        
    if current_para:
        text_block = " ".join(current_para)
        story.append(Paragraph(process_text(text_block), body_style))
        
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
