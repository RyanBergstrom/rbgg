"""Repair the consolidated README from its cached PDF extraction and chart tables."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
README = ROOT / "README.md"
STRUCTURED = ROOT / "player_aid_structured_tables.md"
SEPARATOR = "\n\n---\n\n"


def slugify(heading: str) -> str:
    text = re.sub(r"[`*_~]", "", heading).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", "-", text).strip("-") or "section"


def table_blocks(text: str) -> dict[str, str]:
    blocks = re.split(r"(?=^### Structured tables?: )", text, flags=re.MULTILINE)
    result = {}
    for block in blocks:
        match = re.match(r"### Structured tables?: (.+)", block)
        if match:
            result[match.group(1).strip()] = block.strip()
    return result


def append_before_note(section: str, additions: list[str]) -> str:
    addition = "\n\n".join(additions)
    note = "\n\n*Extraction note:"
    if note in section:
        prefix, suffix = section.rsplit(note, 1)
        return prefix.rstrip() + "\n\n" + addition + note + suffix
    return section.rstrip() + "\n\n" + addition + "\n"


def main() -> None:
    text = README.read_text(encoding="utf-8")
    first_document = re.search(r"^## 01\. ", text, re.MULTILINE)
    if not first_document:
        raise SystemExit("Could not locate the cached first PDF section in README.md")
    body = text[first_document.start():].strip()
    documents = body.split(SEPARATOR)
    if len(documents) != 17:
        raise SystemExit(f"Expected 17 cached PDF sections, found {len(documents)}")

    charts1 = next(i for i, section in enumerate(documents) if section.startswith("## 03. FoF Player Aid - Charts & Tables 1.pdf"))
    charts2 = next(i for i, section in enumerate(documents) if section.startswith("## 04. FoF Player Aid - Charts & Tables 2.pdf"))
    blocks = table_blocks(STRUCTURED.read_text(encoding="utf-8"))

    chart1_names = [
        "Engagement Priorities", "Command Limits", "Command Draw Modifiers",
        "Potential Contact Draws", "Spotting Attempt Draw Modifiers",
        "Grenade Attack Eligibility", "Range Abbreviations", "Command Authority",
        "Offensive Mission Signals", "Defensive Mission Signals",
        "Averaging Experience Levels",
    ]
    chart1_additions = [blocks[name] for name in chart1_names if name in blocks]
    if not chart1_additions:
        raise SystemExit("No Chart & Tables 1 transcription blocks found")
    documents[charts1] = append_before_note(documents[charts1], chart1_additions)

    skills = blocks.get("Skills (12.7)")
    if skills:
        documents[charts2] = append_before_note(documents[charts2], [skills])

    body = SEPARATOR.join(documents)
    heading_pattern = re.compile(r"^(#{2,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
    seen: defaultdict[str, int] = defaultdict(int)
    toc_lines = []
    for match in heading_pattern.finditer(body):
        heading = match.group(2).strip()
        anchor = slugify(heading)
        seen[anchor] += 1
        if seen[anchor] > 1:
            anchor = f"{anchor}-{seen[anchor] - 1}"
        toc_lines.append(f"{'  ' * (len(match.group(1)) - 2)}- [{heading}](#{anchor})")

    preface = [
        "# Fields of Fire — Consolidated Reference",
        "This document consolidates text extracted from the PDF rulebooks, campaign books, field manual, and player aids. Structured Markdown transcriptions are added for chart data where available; verify image-dependent details against the linked source PDF.",
        "**Source PDFs:** 17  \n**Extraction:** Cached PyMuPDF + pymupdf4llm extraction; source order is alphabetical.",
        "## Table of Contents\n\n" + "\n".join(toc_lines),
    ]
    README.write_text("\n\n".join(preface) + "\n\n---\n\n" + body + "\n", encoding="utf-8")
    print(f"Repaired {README}: restored title and TOC; attached {len(chart1_additions)} chart-1 tables and the Skills table to the player aids.")


if __name__ == "__main__":
    main()
