"""Render JSON content items into python-docx elements."""

import re
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
from docx.enum.text import WD_ALIGN_PARAGRAPH

from . import styles


def set_run_font(run, font_name: str, size, bold: bool = False):
    """Set font properties on a run."""
    run.font.name = font_name
    run.font.size = size
    run.bold = bold
    # Set East Asian font too for compatibility
    r = run._element
    rPr = r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = parse_xml(f'<w:rFonts {nsdecls("w")} w:ascii="{font_name}" w:hAnsi="{font_name}"/>')
        rPr.insert(0, rFonts)
    else:
        rFonts.set(qn("w:ascii"), font_name)
        rFonts.set(qn("w:hAnsi"), font_name)


def highlight_yellow(run):
    """Apply yellow highlight to a run."""
    rPr = run._element.get_or_add_rPr()
    highlight = parse_xml(f'<w:highlight {nsdecls("w")} w:val="yellow"/>')
    rPr.append(highlight)


def set_cell_shading(cell, color: str):
    """Set cell background color."""
    shading = parse_xml(
        f'<w:shd {nsdecls("w")} w:fill="{color}" w:val="clear"/>'
    )
    cell._tc.get_or_add_tcPr().append(shading)


def add_markdown_runs(paragraph, text: str, base_font: str, base_size, tbc: bool = False):
    """
    Add runs to a paragraph, parsing inline markdown:
      **bold** -> bold run
      `code`   -> monospace run
      plain    -> normal run
    """
    pattern = re.compile(r'(\*\*[^*]+\*\*|`[^`]+`)')
    parts = pattern.split(text)
    any_tbc = tbc or "[TBC" in text
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = paragraph.add_run(part[2:-2])
            set_run_font(run, base_font, base_size, bold=True)
        elif part.startswith('`') and part.endswith('`'):
            run = paragraph.add_run(part[1:-1])
            set_run_font(run, 'Courier New', base_size)
        else:
            run = paragraph.add_run(part)
            set_run_font(run, base_font, base_size)
        if any_tbc:
            highlight_yellow(run)


def render_paragraph(doc, item: dict):
    """Render a paragraph content item."""
    text = item.get("text", "")
    p = doc.add_paragraph()
    add_markdown_runs(p, text, styles.BODY_FONT, styles.BODY_SIZE, tbc=item.get("tbc", False))
    p.paragraph_format.space_after = styles.BODY_SPACE_AFTER


def render_heading(doc, item: dict, section_number: str = ""):
    """Render a heading content item (levels 3-5 for sub-headings within sections)."""
    text = item.get("text", "")
    level = item.get("level", 3)

    # Map level to Word heading level
    heading_level = min(level, 5)
    p = doc.add_heading(text, level=heading_level)

    # Override font to Arial
    for run in p.runs:
        size_map = {3: styles.HEADING3_SIZE, 4: styles.HEADING4_SIZE, 5: styles.HEADING5_SIZE}
        set_run_font(run, styles.HEADING_FONT, size_map.get(level, styles.HEADING4_SIZE), bold=True)


def render_bullet_list(doc, item: dict):
    """Render a bullet list."""
    for entry in item.get("items", []):
        # LLM sometimes generates nested content dicts instead of plain strings
        if isinstance(entry, dict):
            sub_items = entry.get("items")
            if sub_items:
                render_bullet_list(doc, entry)
                continue
            text = entry.get("text", str(entry))
        else:
            text = str(entry)
        p = doc.add_paragraph(style="List Bullet")
        p.clear()
        add_markdown_runs(p, text, styles.BODY_FONT, styles.BODY_SIZE)


def render_numbered_list(doc, item: dict):
    """Render a numbered list."""
    for entry in item.get("items", []):
        if isinstance(entry, dict):
            text = entry.get("text", str(entry))
        else:
            text = str(entry)
        p = doc.add_paragraph(style="List Number")
        p.clear()
        add_markdown_runs(p, text, styles.BODY_FONT, styles.BODY_SIZE)


def render_table(doc, item: dict):
    """Render a table (standard or decision_table)."""
    headers = item.get("headers", [])
    rows = item.get("rows", [])

    if not headers:
        return

    num_cols = len(headers)
    table = doc.add_table(rows=1 + len(rows), cols=num_cols)
    table.style = "Table Grid"

    # Set table width to full page width
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else parse_xml(f'<w:tblPr {nsdecls("w")}/>')
    tblW = parse_xml(f'<w:tblW {nsdecls("w")} w:w="9360" w:type="dxa"/>')
    tblPr.append(tblW)

    # Header row
    for i, header_text in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(str(header_text))
        set_run_font(run, styles.HEADING_FONT, styles.TABLE_HEADER_SIZE, bold=True)
        set_cell_shading(cell, styles.TABLE_HEADER_FILL)

    # Data rows
    for row_idx, row_data in enumerate(rows):
        # Normalize: LLM sometimes generates rows as dicts instead of lists
        if isinstance(row_data, dict):
            if "cells" in row_data:
                # {"cells": [...], "tbc": True} format
                row_data = row_data["cells"]
            elif "conditions" in row_data:
                # decision_table format: {"conditions": [...], "action": "..."}
                row_data = list(row_data["conditions"]) + [row_data.get("action", "")]
            else:
                # {"header_name": "value", ...} format
                row_data = [row_data.get(h, "") for h in headers]
        elif not isinstance(row_data, list):
            continue
        for col_idx, cell_text in enumerate(row_data):
            if col_idx >= num_cols:
                break
            cell = table.rows[row_idx + 1].cells[col_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            text = str(cell_text) if cell_text is not None else ""
            run = p.add_run(text)
            set_run_font(run, styles.BODY_FONT, styles.TABLE_BODY_SIZE)

            if "[TBC" in text:
                highlight_yellow(run)

    # Add spacing after table
    doc.add_paragraph()


def render_note(doc, item: dict):
    """Render a Note callout."""
    p = doc.add_paragraph()
    run_label = p.add_run("Note: ")
    set_run_font(run_label, styles.BODY_FONT, styles.BODY_SIZE, bold=True)

    text = item.get("text", "")
    run_text = p.add_run(text)
    set_run_font(run_text, styles.BODY_FONT, styles.BODY_SIZE)
    p.paragraph_format.left_indent = Inches(0.5)


def render_figure_placeholder(doc, item: dict):
    """Render a figure placeholder (highlighted for visibility)."""
    text = item.get("text", f"[Figure: Placeholder]")
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, styles.BODY_FONT, styles.BODY_SIZE)
    highlight_yellow(run)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def render_content_item(doc, item: dict, section_number: str = ""):
    """Dispatch a content item to the appropriate renderer."""
    if not isinstance(item, dict):
        return

    item_type = item.get("type", "paragraph")

    if item_type == "paragraph":
        render_paragraph(doc, item)
    elif item_type == "heading":
        render_heading(doc, item, section_number)
    elif item_type == "bullet_list":
        render_bullet_list(doc, item)
    elif item_type == "numbered_list":
        render_numbered_list(doc, item)
    elif item_type in ("table", "decision_table"):
        render_table(doc, item)
    elif item_type == "note":
        render_note(doc, item)
    elif item_type == "figure_placeholder":
        render_figure_placeholder(doc, item)
    else:
        # Unknown type — render as paragraph
        render_paragraph(doc, {"text": item.get("text", str(item)), "tbc": item.get("tbc")})
