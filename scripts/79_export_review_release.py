#!/usr/bin/env python3
"""Export the evidence-frozen main manuscript as an editable review document.

Conditional author declarations remain in the canonical manuscript and are
deliberately omitted from this reader-facing review copy until confirmed.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "manuscript/SUBMISSION_MANUSCRIPT.md"
BIB = ROOT / "manuscript/REFERENCE_LIBRARY.bib"
CAPTIONS = ROOT / "manuscript/FIGURE_CAPTIONS.md"
REGISTRY = ROOT / "manuscript/FIGURE_CLAIM_REGISTRY.csv"
OUT = ROOT / "release/2026-09-23/Delhi_NCR_full_research_manuscript.docx"


def bib_entries() -> dict[str, dict[str, str]]:
    text = BIB.read_text()
    starts = list(re.finditer(r"^@\w+\{([^,]+),", text, flags=re.M))
    result: dict[str, dict[str, str]] = {}
    for i, match in enumerate(starts):
        block = text[match.end() : starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        fields = dict(re.findall(r"^\s*(\w+)\s*=\s*\{(.*)\}\s*,?\s*$", block, flags=re.M))
        result[match.group(1)] = fields
    return result


def author_year(key: str, entries: dict[str, dict[str, str]]) -> str:
    entry = entries[key]
    people = [p.strip() for p in entry.get("author", "").split(" and ")]
    first = people[0].split(",")[0].strip() if people else key
    name = first + (" et al." if len(people) > 2 else (" & " + people[1].split(",")[0].strip() if len(people) == 2 else ""))
    return f"{name}, {entry.get('year', 'n.d.')}"


def clean(text: str, entries: dict[str, dict[str, str]]) -> str:
    text = re.sub(r"<!--.*?-->", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)

    def cite(match: re.Match[str]) -> str:
        keys = re.findall(r"@([A-Za-z0-9_]+)", match.group(1))
        return "(" + "; ".join(author_year(k, entries) for k in keys) + ")"

    text = re.sub(r"\[(@[^\]]+)\]", cite, text)
    text = text.replace("`", "").replace("**", "").replace("*", "")
    return text.strip()


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_border(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for side in ("top", "left", "bottom", "right"):
        edge = OxmlElement(f"w:{side}")
        edge.set(qn("w:val"), "single")
        edge.set(qn("w:sz"), "4")
        edge.set(qn("w:color"), "D9D9D9")
        borders.append(edge)


def make_table(doc: Document, lines: list[str], entries: dict[str, dict[str, str]]) -> None:
    rows = [[clean(part, entries) for part in line.strip().strip("|").split("|")] for line in lines]
    rows = [row for row in rows if not all(re.fullmatch(r":?-+:?", cell.replace(" ", "")) for cell in row)]
    if not rows:
        return
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.autofit = False
    if len(rows[0]) == 5 and rows[0][-1] == "Status":
        widths = [0.55, 1.22, 1.22, 0.74, 3.10]
    elif len(rows[0]) == 3:
        widths = [2.20, 1.45, 3.18]
    else:
        widths = [6.83 / len(rows[0])] * len(rows[0])
    for column, width in zip(table.columns, widths):
        column.width = Inches(width)
    for ri, row in enumerate(rows):
        for ci, value in enumerate(row):
            cell = table.cell(ri, ci)
            cell.width = Inches(widths[ci])
            if rows[0][-1] == "Status" and ci == len(row) - 1:
                value = value.replace("_", " ")
            cell.text = value
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_border(cell)
            set_cell_shading(cell, "E7EBEF" if ri == 0 else ("F7F9FB" if ri % 2 == 0 else "FFFFFF"))
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(3)
                paragraph.paragraph_format.space_before = Pt(3)
                if ci < len(row) - 1 and re.fullmatch(r"[+−-]?[\d.,]+(?:[–-][\d.,]+)?", value):
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                for run in paragraph.runs:
                    run.font.size = Pt(8.5)
                    if ri == 0:
                        run.bold = True
        if ri == 0:
            tr_pr = table.rows[ri]._tr.get_or_add_trPr()
            header = OxmlElement("w:tblHeader")
            header.set(qn("w:val"), "true")
            tr_pr.append(header)
        tr_pr = table.rows[ri]._tr.get_or_add_trPr()
        no_split = OxmlElement("w:cantSplit")
        tr_pr.append(no_split)
    doc.add_paragraph()


def figure_captions() -> dict[str, str]:
    source = CAPTIONS.read_text()
    blocks = re.split(r"(?=^## F\d+\b)", source, flags=re.M)
    result = {}
    for block in blocks:
        match = re.match(r"## (F\d+)", block)
        if not match:
            continue
        paragraphs = [x.strip() for x in block.split("\n\n") if x.strip()]
        lead = next((p for p in paragraphs if p.startswith("**")), "")
        result[match.group(1)] = lead.replace("**", "").replace("*", "")
    return result


def add_figures(doc: Document, entries: dict[str, dict[str, str]]) -> None:
    captions = figure_captions()
    with REGISTRY.open(newline="") as handle:
        figures = [row for row in csv.DictReader(handle) if row["placement"] == "main"]
    for index, row in enumerate(figures):
        doc.add_page_break()
        if index == 0:
            doc.add_heading("Figures", level=1)
        image_path = ROOT / row["source_paths"].split(";")[0]
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
        doc.add_picture(str(image_path), width=Inches(6.45))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        caption = captions.get(row["source_figure"], row["scientific_question"])
        paragraph = doc.add_paragraph(style="Caption")
        paragraph.add_run(f"Figure {row['submission_id'][1:]}. ").bold = True
        paragraph.add_run(clean(caption, entries))


def add_references(doc: Document, used: list[str], entries: dict[str, dict[str, str]]) -> None:
    doc.add_heading("References", level=1)
    for key in used:
        e = entries[key]
        author = e.get("author", "").replace(" and ", "; ").replace("{", "").replace("}", "")
        title = e.get("title", "").replace("{", "").replace("}", "")
        journal = e.get("journal") or e.get("booktitle") or ""
        journal = journal.replace("{", "").replace("}", "").replace(r"\&", "&")
        volume = e.get("volume", "")
        pages = e.get("pages", "")
        year = e.get("year", "")
        doi = e.get("doi", "")
        parts = [f"{author} ({year}). {title}.", journal + (f", {volume}" if volume else "") + (f", {pages}" if pages else "") + "."]
        if doi:
            parts.append(f"https://doi.org/{doi}")
        paragraph = doc.add_paragraph(" ".join(parts))
        paragraph.paragraph_format.space_after = Pt(5)


def main() -> int:
    entries = bib_entries()
    source = SOURCE.read_text()
    used = list(dict.fromkeys(
        key
        for group in re.findall(r"\[(@[^\]]+)\]", source)
        for key in re.findall(r"@([A-Za-z0-9_]+)", group)
    ))
    missing = [key for key in used if key not in entries]
    if missing:
        raise ValueError(f"Missing bibliography entries: {missing}")

    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.68)
    section.left_margin = Inches(0.82)
    section.right_margin = Inches(0.82)
    styles = doc.styles
    styles["Normal"].font.name = "Cambria"
    styles["Normal"].font.size = Pt(10.5)
    styles["Normal"].font.color.rgb = RGBColor(0, 0, 0)
    styles["Normal"].paragraph_format.space_after = Pt(5)
    styles["Normal"].paragraph_format.line_spacing = 1.12
    for name, size, before, after in (("Title", 17, 0, 11), ("Heading 1", 12, 12, 6), ("Heading 2", 10.5, 9, 4)):
        style = styles[name]
        style.font.name = "Cambria"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
    title_style = styles["Title"]
    title_style.base_style = styles["Normal"]
    ppr = title_style.element.get_or_add_pPr()
    border = ppr.find(qn("w:pBdr"))
    if border is not None:
        ppr.remove(border)
    styles["Caption"].font.name = "Cambria"
    styles["Caption"].font.size = Pt(9)
    styles["Caption"].font.bold = False
    styles["Caption"].font.color.rgb = RGBColor(0, 0, 0)
    styles["Caption"].paragraph_format.space_after = Pt(10)

    skip_headings = {
        "Author contributions (CRediT)",
        "Funding",
        "Declaration of generative AI and AI-assisted technologies in the manuscript preparation process",
    }
    skip = False
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## "):
            skip = line[3:].strip() in skip_headings
        if skip:
            i += 1
            continue
        if line.startswith("| "):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            make_table(doc, table_lines, entries)
            continue
        if line.startswith("# "):
            doc.add_paragraph(clean(line[2:], entries), style="Title")
        elif line.startswith("## "):
            doc.add_heading(clean(line[3:], entries), level=1)
        elif line.startswith("### "):
            doc.add_heading(clean(line[4:], entries), level=2)
        elif line:
            paragraph = doc.add_paragraph(clean(line, entries))
            if line.startswith("**Table "):
                paragraph.style = "Caption"
                paragraph.paragraph_format.keep_with_next = True
            elif line.startswith("**Authors:") or line.startswith("**Affiliation:") or line.startswith("**Corresponding author:"):
                paragraph.paragraph_format.space_after = Pt(2)
        i += 1

    add_references(doc, used, entries)
    add_figures(doc, entries)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)
    print(f"references={len(used)} main_figures=8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
