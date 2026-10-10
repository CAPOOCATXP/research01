# -*- coding: utf-8 -*-
"""Convert a Markdown file to a formatted DOCX (then PDF via the bundled LibreOffice Kit).

Usage:
    python md2docx.py <input.md> <output.docx>

Supports: ATX headings, **bold** / *italic* / `code`, blockquotes, bullet and ordered
lists, Markdown tables (a wide table switches that section to landscape), footer page
numbers, and CJK eastAsia font assignment.
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

EA_BODY = "宋体"
EA_HEAD = "微软雅黑"
LAT_BODY = "Segoe UI"
LAT_HEAD = "Segoe UI Semibold"
MONO = "Consolas"
BODY_PT = 10.0
TABLE_PT = 8.0

INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*\n]+?\*|`[^`]+`)")

# Table specs keyed by their first header cell. Widths are centimetres and must fit the
# usable width of the section (portrait A4 with 2 cm margins -> 17.0; landscape -> 26.1).
TABLE_SPECS = {
    "任务": dict(widths=[8.0, 1.1, 4.6, 3.9], landscape=False, size=8.0),
    "分辨率": dict(widths=[2.2, 2.0, 2.2, 2.2, 9.0], landscape=False, size=8.0),
    "#": dict(widths=[0.9, 8.4, 5.4, 2.3], landscape=False, size=9.0),
}


def style_run(run, latin=LAT_BODY, ea=EA_BODY, size=BODY_PT, bold=None, italic=None):
    run.font.name = latin
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    rFonts.set(qn("w:ascii"), latin)
    rFonts.set(qn("w:hAnsi"), latin)
    rFonts.set(qn("w:eastAsia"), ea)
    run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    return run


def add_rich(par, text, size=BODY_PT, bold=False, italic=False,
             latin=LAT_BODY, ea=EA_BODY, color=None):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            r = par.add_run(part[2:-2])
            style_run(r, latin, ea, size, True, italic)
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            r = par.add_run(part[1:-1])
            style_run(r, latin, ea, size, bold, True)
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            r = par.add_run(part[1:-1])
            style_run(r, MONO, MONO, size - 0.5, False, None)
            r.font.color.rgb = RGBColor(0xB0, 0x30, 0x30)
        else:
            r = par.add_run(part)
            style_run(r, latin, ea, size, bold, italic)
        if color:
            r.font.color.rgb = color
    return par


def para(doc, text="", size=BODY_PT, bold=False, italic=False, align=None,
         space_before=0, space_after=4, indent=None, latin=LAT_BODY, ea=EA_BODY,
         color=None, line_spacing=1.10):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    if indent is not None:
        pf.left_indent = Cm(indent)
    if align is not None:
        p.alignment = align
    if text:
        add_rich(p, text, size, bold, italic, latin, ea, color)
    return p


def shade_cell(cell, fill="EFEFEF"):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def set_page_number_footer(section):
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    style_run(r, LAT_BODY, EA_BODY, 8.5)
    begin = OxmlElement("w:fldChar"); begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve"); instr.text = "PAGE"
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    r._r.append(begin); r._r.append(instr); r._r.append(end)


def configure_section(section, landscape=False):
    if landscape:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = Cm(29.7), Cm(21.0)
        section.left_margin = section.right_margin = Cm(1.8)
        section.top_margin = section.bottom_margin = Cm(1.5)
    else:
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width, section.page_height = Cm(21.0), Cm(29.7)
        section.left_margin = section.right_margin = Cm(1.7)
        section.top_margin = section.bottom_margin = Cm(1.5)


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_sep(line):
    return bool(re.fullmatch(r"\|[\s:\-|]+\|", line.strip()))


def build(doc, lines):
    i, n = 0, len(lines)
    while i < n:
        stripped = lines[i].strip()
        if not stripped or re.fullmatch(r"-{3,}", stripped):
            i += 1
            continue

        # table
        if stripped.startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                if not is_sep(lines[i]):
                    block.append(split_row(lines[i]))
                i += 1
            header = block[0][0].replace("**", "")
            spec = TABLE_SPECS.get(header, dict(widths=None, landscape=False, size=TABLE_PT))
            if spec["landscape"]:
                configure_section(doc.add_section(WD_SECTION.NEW_PAGE), landscape=True)
            t = doc.add_table(rows=0, cols=len(block[0]))
            t.style = "Table Grid"
            t.alignment = WD_TABLE_ALIGNMENT.CENTER
            t.autofit = False
            for r_idx, row in enumerate(block):
                cells = t.add_row().cells
                for c_idx, text in enumerate(row):
                    cell = cells[c_idx]
                    cell.text = ""
                    p = cell.paragraphs[0]
                    p.paragraph_format.space_before = Pt(1)
                    p.paragraph_format.space_after = Pt(1)
                    p.paragraph_format.line_spacing = 1.05
                    add_rich(p, text, size=spec["size"], bold=(r_idx == 0),
                             latin=LAT_HEAD if r_idx == 0 else LAT_BODY,
                             ea=EA_HEAD if r_idx == 0 else EA_BODY)
                    if r_idx == 0:
                        shade_cell(cell)
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if r_idx == 0:
                    repeat_header(t.rows[0])
            if spec["widths"] and len(spec["widths"]) == len(block[0]):
                for row in t.rows:
                    for idx, cell in enumerate(row.cells):
                        cell.width = Cm(spec["widths"][idx])
            if spec["landscape"]:
                configure_section(doc.add_section(WD_SECTION.NEW_PAGE), landscape=False)
            continue

        # headings
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level, text = len(m.group(1)), m.group(2)
            if level == 1:
                para(doc, text, size=17, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER,
                     space_after=12, latin=LAT_HEAD, ea=EA_HEAD)
            elif level == 2:
                para(doc, text, size=13, bold=True, space_before=12, space_after=5,
                     latin=LAT_HEAD, ea=EA_HEAD)
            else:
                para(doc, text, size=11.5, bold=True, space_before=9, space_after=4,
                     latin=LAT_HEAD, ea=EA_HEAD)
            i += 1
            continue

        # blockquote
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            for b in buf:
                if b:
                    para(doc, b, size=9.5, italic=True, indent=0.5, space_after=2,
                         color=RGBColor(0x44, 0x44, 0x44))
            continue

        # bullets
        if re.match(r"^[-*]\s+", stripped):
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.line_spacing = 1.18
            add_rich(p, re.sub(r"^[-*]\s+", "", stripped))
            i += 1
            continue

        # ordered list (keep the literal number, hanging indent)
        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            p = doc.add_paragraph()
            pf = p.paragraph_format
            pf.left_indent = Cm(0.75)
            pf.first_line_indent = Cm(-0.75)
            pf.space_after = Pt(2)
            pf.line_spacing = 1.18
            add_rich(p, m.group(1) + ". " + m.group(2))
            i += 1
            continue

        para(doc, stripped)
        i += 1


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    lines = src.read_text(encoding="utf-8").splitlines()

    doc = Document()
    configure_section(doc.sections[0], landscape=False)
    set_page_number_footer(doc.sections[0])

    normal = doc.styles["Normal"]
    normal.font.name = LAT_BODY
    normal.font.size = Pt(BODY_PT)
    rpr = normal.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts"); rpr.insert(0, rf)
    rf.set(qn("w:ascii"), LAT_BODY); rf.set(qn("w:hAnsi"), LAT_BODY); rf.set(qn("w:eastAsia"), EA_BODY)

    build(doc, lines)
    doc.save(str(out))
    print("OK -> %s  paragraphs=%d tables=%d sections=%d"
          % (out, len(doc.paragraphs), len(doc.tables), len(doc.sections)))


if __name__ == "__main__":
    main()
