"""Markdown preprocessing and structure-aware chunking for RAG ingestion."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, TypedDict


class MarkdownHeading(TypedDict):
    """Structured metadata for a Markdown heading."""

    line_number: int
    level: int
    text: str


class MarkdownBlock(TypedDict):
    """A document block that should usually stay together during chunking."""

    type: str
    text: str
    section_title: str


_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_MD_LIST_RE = re.compile(
    r"^(\s*)((?:[-*+])|(?:\d+[\.)])|(?:[A-Za-z][\.)])|(?:[ivxlcdmIVXLCDM]+[\.)]))\s+(.*\S)\s*$"
)
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
_PAGE_NOISE_RE = re.compile(r"^\s*(?:page\s*)?\d+\s*(?:of|/)\s*\d+\s*$", re.IGNORECASE)
_SINGLE_PAGE_RE = re.compile(r"^\s*page\s+\d+\s*$", re.IGNORECASE)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_OCR_JUNK_RE = re.compile(r"([@%#\ufffd\u25a1])\1{4,}")


def preprocess_markdown(markdown: str) -> str:
    """Clean Markdown while preserving headings, tables, code blocks, and lists."""

    if not markdown:
        return ""

    cleaned = normalize_markdown_newlines(markdown)
    cleaned = remove_markdown_boilerplate(cleaned)
    cleaned = remove_markdown_ocr_artifacts(cleaned)
    cleaned = normalize_markdown_whitespace(cleaned)
    cleaned = normalize_markdown_bullets(cleaned)
    cleaned = preserve_markdown_lists(cleaned)
    cleaned = preserve_markdown_tables(cleaned)
    return cleaned.strip()


def normalize_markdown_newlines(markdown: str) -> str:
    """Normalize line endings and remove non-breaking spaces."""

    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n")
    return markdown.replace("\u00a0", " ")


def remove_markdown_boilerplate(markdown: str) -> str:
    """Remove obvious Markdown/PDF conversion noise without touching content."""

    markdown = _HTML_COMMENT_RE.sub("", markdown)
    lines = markdown.splitlines()
    counts = Counter(_canonical_line(line) for line in lines if line.strip())

    output: list[str] = []
    in_code = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            output.append(line.rstrip())
            continue

        if in_code:
            output.append(line.rstrip())
            continue

        if not stripped:
            output.append("")
            continue

        canonical = _canonical_line(line)
        if _PAGE_NOISE_RE.match(stripped) or _SINGLE_PAGE_RE.match(stripped):
            continue
        if stripped.lower() in {"confidential", "proprietary", "internal use only"}:
            continue
        if counts[canonical] >= 3 and len(stripped) <= 80 and not _is_markdown_heading(stripped):
            continue

        output.append(line.rstrip())

    return _collapse_blank_lines(output)


def remove_markdown_ocr_artifacts(markdown: str) -> str:
    """Remove obvious OCR corruption while keeping Markdown syntax intact."""

    output: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if re.fullmatch(r"[@%\ufffd\u25a1]{3,}", stripped):
            continue
        output.append(_OCR_JUNK_RE.sub("", line).rstrip())
    return "\n".join(output).strip()


def normalize_markdown_whitespace(markdown: str) -> str:
    """Collapse noisy inline spacing without breaking Markdown tables or code."""

    output: list[str] = []
    in_code = False

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            output.append(line.rstrip())
            continue

        if in_code or _is_markdown_table_line(line):
            output.append(line.rstrip())
            continue

        leading = re.match(r"^\s*", line).group(0).replace("\t", "    ")
        content = line[len(leading) :]
        content = re.sub(r"[ \t]+", " ", content).strip()
        output.append(f"{leading}{content}".rstrip())

    return _collapse_blank_lines(output)


def normalize_markdown_bullets(markdown: str) -> str:
    """Normalize common bullet glyphs to Markdown ``*`` list items."""

    output: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^(\s*)[\u2022\u25e6\u25aa]\s+(.*\S)\s*$", line)
        if match:
            indent, item = match.groups()
            output.append(f"{indent}* {item}")
        else:
            output.append(line.rstrip())
    return "\n".join(output).strip()


def preserve_markdown_lists(markdown: str) -> str:
    """Keep Markdown list blocks isolated from surrounding paragraphs."""

    blocks = split_markdown_blocks(markdown)
    return "\n\n".join(block["text"] for block in blocks).strip()


def preserve_markdown_tables(markdown: str) -> str:
    """Normalize table spacing and preserve table blocks as Markdown tables."""

    blocks = split_markdown_blocks(markdown)
    output: list[str] = []

    for block in blocks:
        if block["type"] == "table":
            output.append(_normalize_markdown_table(block["text"]))
        else:
            output.append(block["text"])

    return "\n\n".join(part.strip() for part in output if part.strip()).strip()


def detect_markdown_headings(markdown: str) -> list[MarkdownHeading]:
    """Return Markdown headings with line numbers and heading levels."""

    headings: list[MarkdownHeading] = []
    for line_number, line in enumerate(markdown.splitlines(), start=1):
        match = _MD_HEADING_RE.match(line.strip())
        if match:
            hashes, title = match.groups()
            headings.append(
                {
                    "line_number": line_number,
                    "level": len(hashes),
                    "text": title.strip(),
                }
            )
    return headings


def split_markdown_blocks(markdown: str) -> list[MarkdownBlock]:
    """Split Markdown into paragraphs, headings, lists, tables, and code blocks."""

    lines = markdown.splitlines()
    blocks: list[MarkdownBlock] = []
    current_section = ""
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        heading = _MD_HEADING_RE.match(stripped)
        if heading:
            current_section = heading.group(2).strip()
            blocks.append({"type": "heading", "text": stripped, "section_title": current_section})
            index += 1
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            block_lines, index = _consume_code_block(lines, index)
            blocks.append(
                {"type": "code", "text": "\n".join(block_lines), "section_title": current_section}
            )
            continue

        if _is_markdown_table_line(line):
            block_lines, index = _consume_table_block(lines, index)
            blocks.append(
                {"type": "table", "text": "\n".join(block_lines), "section_title": current_section}
            )
            continue

        if _is_markdown_list_item(stripped):
            block_lines, index = _consume_list_block(lines, index)
            blocks.append(
                {"type": "list", "text": "\n".join(block_lines), "section_title": current_section}
            )
            continue

        block_lines, index = _consume_paragraph(lines, index)
        blocks.append(
            {"type": "paragraph", "text": " ".join(block_lines), "section_title": current_section}
        )

    return blocks


def chunk_markdown_by_structure(
    markdown: str,
    *,
    document_title: str = "",
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> list[str]:
    """Create RAG chunks while keeping headings, lists, and tables together."""

    blocks = split_markdown_blocks(markdown)
    chunks: list[str] = []
    current_parts: list[str] = []
    current_section = ""

    for block in blocks:
        text = block["text"].strip()
        if not text:
            continue

        if block["type"] == "heading":
            current_section = _strip_markdown_heading(text)

        candidate = "\n\n".join(current_parts + [text]).strip()
        if current_parts and len(candidate) > max_chars:
            chunks.append(_with_context("\n\n".join(current_parts), document_title, current_section))
            current_parts = []

        if len(text) > max_chars and block["type"] not in {"table", "list", "code"}:
            chunks.extend(
                _with_context(part, document_title, current_section)
                for part in _split_long_text(text, max_chars, overlap_chars)
            )
        else:
            current_parts.append(text)

    if current_parts:
        chunks.append(_with_context("\n\n".join(current_parts), document_title, current_section))

    return [chunk for chunk in chunks if chunk.strip()]


def _canonical_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def _collapse_blank_lines(lines: Iterable[str]) -> str:
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _is_markdown_heading(line: str) -> bool:
    return bool(_MD_HEADING_RE.match(line.strip()))


def _is_markdown_list_item(line: str) -> bool:
    return bool(_MD_LIST_RE.match(line))


def _is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or _is_markdown_list_item(stripped):
        return False
    if _TABLE_SEPARATOR_RE.match(stripped):
        return True
    if "|" not in stripped:
        return False
    cells = _split_markdown_table_row(stripped)
    return len(cells) >= 2 and any(cell for cell in cells)


def _consume_code_block(lines: list[str], start: int) -> tuple[list[str], int]:
    fence = lines[start].strip()[:3]
    output = [lines[start].rstrip()]
    index = start + 1
    while index < len(lines):
        output.append(lines[index].rstrip())
        if lines[index].strip().startswith(fence):
            index += 1
            break
        index += 1
    return output, index


def _consume_table_block(lines: list[str], start: int) -> tuple[list[str], int]:
    output: list[str] = []
    index = start
    while index < len(lines) and _is_markdown_table_line(lines[index]):
        output.append(lines[index].rstrip())
        index += 1
    return output, index


def _consume_list_block(lines: list[str], start: int) -> tuple[list[str], int]:
    output: list[str] = []
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if not _is_markdown_list_item(next_line.strip()):
                break
            output.append("")
            index += 1
            continue
        if _is_markdown_list_item(stripped) or lines[index].startswith((" ", "\t")):
            output.append(lines[index].rstrip())
            index += 1
            continue
        break
    return output, index


def _consume_paragraph(lines: list[str], start: int) -> tuple[list[str], int]:
    output: list[str] = []
    index = start
    while index < len(lines):
        stripped = lines[index].strip()
        if (
            not stripped
            or _is_markdown_heading(stripped)
            or _is_markdown_table_line(lines[index])
            or _is_markdown_list_item(stripped)
            or stripped.startswith(("```", "~~~"))
        ):
            break
        output.append(stripped)
        index += 1
    return output, index


def _normalize_markdown_table(table_text: str) -> str:
    rows = [_split_markdown_table_row(line) for line in table_text.splitlines()]
    rows = [row for row in rows if row]
    if len(rows) < 2:
        return table_text.strip()

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]

    has_separator = any(all(_is_separator_cell(cell) for cell in row) for row in rows[1:2])
    if not has_separator:
        rows.insert(1, ["---"] * width)

    return "\n".join(_markdown_row(row) for row in rows)


def _split_markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator_cell(cell: str) -> bool:
    return bool(re.fullmatch(r":?-{3,}:?", cell.strip()))


def _markdown_row(values: Iterable[str]) -> str:
    escaped = [value.replace("|", "\\|").strip() for value in values]
    return "| " + " | ".join(escaped) + " |"


def _strip_markdown_heading(text: str) -> str:
    match = _MD_HEADING_RE.match(text.strip())
    return match.group(2).strip() if match else ""


def _with_context(text: str, document_title: str, section_title: str) -> str:
    metadata: list[str] = []
    if document_title.strip():
        metadata.append(f"Document Title: {document_title.strip()}")
    if section_title.strip():
        metadata.append(f"Section Title: {section_title.strip()}")
    return "\n".join(metadata + ["", text.strip()]).strip() if metadata else text.strip()


def _split_long_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            sentence_end = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if sentence_end > start + max_chars // 2:
                end = sentence_end + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap_chars, start + 1)
    return chunks


if __name__ == "__main__":
    sample = """
# Leave Policy

Employee      | Salary
---           | ---
John          | 50000

• Annual leave
  ◦ Carry forward rules
"""
    cleaned = preprocess_markdown(sample)
    print(cleaned)
    print(chunk_markdown_by_structure(cleaned, document_title="Employee Handbook"))
