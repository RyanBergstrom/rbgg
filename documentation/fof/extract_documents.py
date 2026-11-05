"""Build a single Markdown reference from every PDF in this folder.

Requires the packages listed in requirements.txt. Run from this folder with:
    python extract_documents.py
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import fitz
import pymupdf4llm

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "README.md"
PDFS = sorted(ROOT.glob("*.pdf"), key=lambda path: path.name.casefold())


def document_kind(name: str) -> str:
    lower = name.casefold()
    if "player aid" in lower or "player aId".casefold() in lower or "player aid" in lower:
        return "Player aid / reference sheet"
    if "field_manual" in lower or "field manual" in lower:
        return "Training manual"
    if "campaign" in lower or "stand-alone" in lower or "mission" in lower:
        return "Campaign / mission book"
    if "clarification" in lower or "errata" in lower:
        return "Errata / rules clarifications"
    if "rule" in lower:
        return "Series rulebook"
    return "Game reference document"


def slugify(heading: str) -> str:
    text = re.sub(r"[`*_~]", "", heading).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return re.sub(r"[\s]+", "-", text).strip("-") or "section"


def build_readme() -> None:
    if not PDFS:
        raise SystemExit(f"No PDF files found in {ROOT}")

    sections: list[str] = [
        "# Fields of Fire — Consolidated Reference\n",
        "This document consolidates the text and table-oriented content extracted from the PDF rulebooks, campaign books, field manual, and player aids in this folder. It is intended as a searchable reference for software implementation; verify ambiguous or image-dependent details against the linked source PDF.\n",
        f"**Source PDFs:** {len(PDFS)}  \n**Extraction:** PyMuPDF + pymupdf4llm; source order is alphabetical.\n",
        "## Table of Contents\n",
    ]
    body_sections: list[str] = []
    for index, path in enumerate(PDFS, start=1):
        doc = fitz.open(path)
        metadata = doc.metadata or {}
        chunks = pymupdf4llm.to_markdown(
            doc,
            page_chunks=True,
            table_strategy="lines",
            show_progress=False,
            use_ocr=False,
        )
        page_count = len(doc)
        doc.close()

        source_link = quote(path.name)
        title = metadata.get("title") or "(PDF metadata has no title)"
        author = metadata.get("author") or "(not specified in PDF metadata)"
        file_section = [
            f"## {index:02d}. {path.name}\n",
            f"**Document type:** {document_kind(path.name)}  \n"
            f"**PDF title:** {title}  \n"
            f"**Author metadata:** {author}  \n"
            f"**Pages:** {page_count}  \n"
            f"**File size:** {path.stat().st_size:,} bytes  \n"
            f"**Source:** [{path.name}]({source_link})\n",
        ]

        for page_index, chunk in enumerate(chunks, start=1):
            page_text = chunk.get("text", "").strip()
            file_section.append(f"### Page {page_index}\n")
            if page_text:
                file_section.append(page_text + "\n")
                if "intentionally omitted" in page_text:
                    file_section.append(
                        "*Extraction note: this page contains visual elements that are not represented "
                        "as text here. Consult the linked source PDF for the complete visual content.*\n"
                    )
            else:
                file_section.append("*(No extractable text detected on this page; consult the source PDF.)*\n")
        if path.name == "FoF Player Aid - Charts & Tables 1.pdf":
            chart_sample = ROOT / "sample_lat_limitations_chart.md"
            if chart_sample.exists():
                sample_text = chart_sample.read_text(encoding="utf-8")
                table_start = sample_text.index("## LAT Limitations Chart (4.2.5)")
                table_end = sample_text.index("### Footnotes")
                file_section.append("### LAT Limitations Chart (4.2.5) — Structured Transcription\n")
                file_section.append(sample_text[table_start:table_end].strip() + "\n")
                footnotes_start = sample_text.index("### Footnotes")
                note_end = sample_text.index("### Common restriction note")
                file_section.append(sample_text[footnotes_start:note_end].strip() + "\n")
        if path.name in {
            "FoF Player Aid - Charts & Tables 1.pdf",
            "FoF Player Aid - Charts & Tables 2.pdf",
        }:
            structured_path = ROOT / "player_aid_structured_tables.md"
            if structured_path.exists():
                structured_text = structured_path.read_text(encoding="utf-8")
                chart2_marker = "### Structured table: VOF, Affected Area, PDF, and Effects"
                if path.name == "FoF Player Aid - Charts & Tables 1.pdf":
                    structured_text = structured_text.split(chart2_marker, maxsplit=1)[0]
                else:
                    structured_text = chart2_marker + structured_text.split(chart2_marker, maxsplit=1)[1]
                file_section.append("### Structured chart and table transcriptions\n")
                file_section.append(structured_text.strip() + "\n")
        body_sections.append("\n".join(file_section))

    body = "\n\n---\n\n".join(body_sections)
    # Build the index only after extraction is complete, so it covers every
    # document, page, and internal heading actually present in the output.
    heading_pattern = re.compile(r"^(#{2,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
    seen: defaultdict[str, int] = defaultdict(int)
    toc_lines: list[str] = []
    for match in heading_pattern.finditer(body):
        level = len(match.group(1))
        heading = match.group(2).strip()
        anchor = slugify(heading)
        seen[anchor] += 1
        if seen[anchor] > 1:
            anchor = f"{anchor}-{seen[anchor]-1}"
        indent = "  " * (level - 2)
        toc_lines.append(f"{indent}- [{heading}](#{anchor})")

    sections[3] = "## Table of Contents\n\n" + "\n".join(toc_lines) + "\n"
    OUTPUT.write_text("\n".join(sections) + "\n\n---\n\n" + body + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} from {len(PDFS)} PDFs ({sum(len(fitz.open(p)) for p in PDFS)} pages).")


if __name__ == "__main__":
    build_readme()
