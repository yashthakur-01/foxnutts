"""Document preprocessing utilities for RAG pipelines.

The functions in this module are intentionally independent and composable.
They avoid third-party dependencies so they can run in lightweight ingestion
jobs before chunking and embedding.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Literal, TypedDict


class HeadingInfo(TypedDict):
    """Structured metadata for a detected heading."""

    line_number: int
    text: str
    level: int
    reason: str


_BULLET_CHARS = "\u2022\u25e6\u25aa*"
_BULLET_RE = re.compile(rf"^(\s*)[{re.escape(_BULLET_CHARS)}]\s+(.*\S)\s*$")
_LIST_RE = re.compile(
    r"^(\s*)((?:[-*+])|(?:\d+[\.)])|(?:[A-Za-z][\.)])|(?:[ivxlcdmIVXLCDM]+[\.)]))\s+(.*\S)\s*$"
)
_PAGE_RE = re.compile(r"^\s*(?:page\s*)?\d+\s*(?:of|/)\s*\d+\s*$", re.IGNORECASE)
_PAGE_SINGLE_RE = re.compile(r"^\s*page\s+\d+\s*$", re.IGNORECASE)
_COPYRIGHT_RE = re.compile(
    r"^\s*(?:copyright|\(c\)|©)\s*(?:\d{4})?.*$", re.IGNORECASE
)
_CONFIDENTIAL_RE = re.compile(
    r"^\s*(?:confidential|proprietary|internal use only|private and confidential)\s*$",
    re.IGNORECASE,
)
_OCR_JUNK_LINE_RE = re.compile(r"^\s*([@%#\u25a1\ufffd])\1{2,}\s*$")
_OCR_JUNK_RUN_RE = re.compile(r"([@%#\u25a1\ufffd])\1{4,}")


def normalize_whitespace(text: str) -> str:
    """Normalize spacing while preserving paragraphs, headings, and lists.

    Excess spaces and tabs within a line are collapsed to one space. Runs of
    three or more newlines are collapsed to two newlines so paragraph breaks
    remain visible.
    """

    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")

    normalized_lines: list[str] = []
    for line in text.split("\n"):
        leading = re.match(r"^\s*", line).group(0)
        content = line[len(leading) :]

        # Preserve indentation for nested lists, but normalize tabs to spaces.
        indent = leading.replace("\t", "    ")
        content = re.sub(r"[ \t]+", " ", content).strip()
        normalized_lines.append(f"{indent}{content}".rstrip())

    normalized = "\n".join(normalized_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def remove_boilerplate(text: str) -> str:
    """Remove obvious page noise and repeated headers or footers.

    The function removes conservative patterns such as page numbers,
    confidentiality labels, copyright notices, and short lines repeated across
    multiple pages. Repeated-line removal is intentionally limited to short
    lines that appear at least three times.
    """

    if not text:
        return ""

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    stripped_counts = Counter(_canonical_line(line) for line in lines if line.strip())

    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        canonical = _canonical_line(line)

        if not stripped:
            cleaned.append("")
            continue

        if _is_obvious_boilerplate(stripped):
            continue

        if (
            stripped_counts[canonical] >= 3
            and len(stripped) <= 80
            and not _looks_like_list_item(stripped)
            and not _looks_like_heading_content(stripped)
        ):
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def normalize_bullets(text: str) -> str:
    """Convert supported bullet glyphs to ``*`` while preserving indentation."""

    if not text:
        return ""

    normalized: list[str] = []
    for line in text.splitlines():
        match = _BULLET_RE.match(line)
        if match:
            indent, item = match.groups()
            normalized.append(f"{indent}* {item}")
        else:
            normalized.append(line)
    return "\n".join(normalized)


def detect_headings(text: str) -> list[HeadingInfo]:
    """Detect likely headings using conservative structural heuristics."""

    if not text:
        return []

    lines = text.splitlines()
    headings: list[HeadingInfo] = []

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or _looks_like_list_item(stripped) or _looks_like_table_row(stripped):
            continue

        previous_blank = index == 0 or not lines[index - 1].strip()
        next_blank = index == len(lines) - 1 or not lines[index + 1].strip()
        word_count = len(stripped.split())

        reason = ""
        if _is_all_caps_heading(stripped):
            reason = "all_caps"
        elif _is_title_case_heading(stripped):
            reason = "title_case"
        elif stripped.endswith(":") and word_count <= 12:
            reason = "ends_with_colon"
        elif previous_blank and next_blank and word_count <= 10 and len(stripped) <= 80:
            reason = "short_line_surrounded_by_blank_lines"

        if reason:
            headings.append(
                {
                    "line_number": index + 1,
                    "text": stripped,
                    "level": _estimate_heading_level(stripped, reason),
                    "reason": reason,
                }
            )

    return headings


def preserve_lists(text: str) -> str:
    """Keep bullet, numbered, and nested list items separated from paragraphs.

    Continuation lines under list items are retained with their indentation.
    Blank lines around list blocks are normalized so later chunking does not
    accidentally merge list items into surrounding prose.
    """

    if not text:
        return ""

    lines = text.splitlines()
    output: list[str] = []
    in_list = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        is_list_item = _looks_like_list_item(stripped)

        if is_list_item and output and output[-1].strip() and not in_list:
            output.append("")

        output.append(line.rstrip())

        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        next_is_list = _looks_like_list_item(next_line.strip())
        next_is_continuation = bool(next_line.startswith((" ", "\t"))) and not next_is_list

        if is_list_item:
            in_list = True
        elif in_list and stripped and not next_is_list and not next_is_continuation:
            in_list = False

        if in_list and not next_is_list and not next_is_continuation and next_line.strip():
            output.append("")

    return _collapse_blank_lines(output)


def preserve_tables(text: str) -> str:
    """Detect simple tables and convert them to key-value or Markdown text.

    Two-column whitespace tables are converted to ``Header: Value`` rows.
    Wider tables are converted to Markdown tables. Existing pipe-delimited
    Markdown tables are left unchanged.
    """

    if not text:
        return ""

    lines = text.splitlines()
    table_blocks = _find_table_blocks(lines)
    if not table_blocks:
        return text

    output: list[str] = []
    cursor = 0

    for block in table_blocks:
        start, end, block_lines = block
        output.extend(lines[cursor:start])
        converted = _convert_table_block(block_lines)
        if converted:
            if output and output[-1].strip():
                output.append("")
            output.extend(converted)
            output.append("")
        else:
            output.extend(block_lines)
        cursor = end

    output.extend(lines[cursor:])
    return _collapse_blank_lines(output)


def remove_ocr_artifacts(text: str) -> str:
    """Remove obvious OCR corruption while preserving valid punctuation."""

    if not text:
        return ""

    cleaned_lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _OCR_JUNK_LINE_RE.match(line):
            continue
        line = _OCR_JUNK_RUN_RE.sub("", line)
        line = re.sub(r"[\ufffd\u25a1]{2,}", "", line)
        cleaned_lines.append(line.rstrip())

    return "\n".join(cleaned_lines).strip()


def enrich_context(text: str, document_title: str, section_title: str) -> str:
    """Prepend document and section metadata to improve retrieval context."""

    metadata: list[str] = []
    if document_title.strip():
        metadata.append(f"Document Title: {document_title.strip()}")
    if section_title.strip():
        metadata.append(f"Section Title: {section_title.strip()}")

    cleaned_text = text.strip()
    if not metadata:
        return cleaned_text
    if not cleaned_text:
        return "\n".join(metadata)
    return "\n".join(metadata) + "\n\n" + cleaned_text


def preprocess_document(text: str) -> str:
    """Run the production preprocessing pipeline and return cleaned text."""

    cleaned = remove_boilerplate(text)
    cleaned = remove_ocr_artifacts(cleaned)
    cleaned = normalize_whitespace(cleaned)
    cleaned = normalize_bullets(cleaned)
    cleaned = preserve_lists(cleaned)
    cleaned = preserve_tables(cleaned)

    # Heading detection is executed here for parity with the pipeline contract.
    # The cleaned text remains the return value expected by chunking pipelines.
    _ = detect_headings(cleaned)

    return cleaned.strip()


def _canonical_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def _is_obvious_boilerplate(line: str) -> bool:
    return bool(
        _PAGE_RE.match(line)
        or _PAGE_SINGLE_RE.match(line)
        or _COPYRIGHT_RE.match(line)
        or _CONFIDENTIAL_RE.match(line)
    )


def _looks_like_list_item(line: str) -> bool:
    return bool(_LIST_RE.match(line))


def _looks_like_heading_content(line: str) -> bool:
    return (
        _is_all_caps_heading(line)
        or _is_title_case_heading(line)
        or (line.endswith(":") and len(line.split()) <= 12)
    )


def _is_all_caps_heading(line: str) -> bool:
    letters = [char for char in line if char.isalpha()]
    return bool(letters) and len(line) <= 100 and line.upper() == line and len(line.split()) <= 12


def _is_title_case_heading(line: str) -> bool:
    words = [word.strip("()[]{}:,-") for word in line.split()]
    meaningful = [word for word in words if any(char.isalpha() for char in word)]
    if not meaningful or len(meaningful) > 12 or len(line) > 100:
        return False
    title_words = sum(1 for word in meaningful if word[:1].isupper())
    return title_words / len(meaningful) >= 0.8


def _estimate_heading_level(text: str, reason: str) -> int:
    if reason == "all_caps":
        return 1
    if text.endswith(":"):
        return 3
    return 2


def _looks_like_table_row(line: str) -> bool:
    if not line.strip() or _looks_like_list_item(line.strip()):
        return False
    if "|" in line and line.count("|") >= 2:
        return True
    return bool(re.search(r"\S\s{2,}\S|\t", line))


def _find_table_blocks(lines: list[str]) -> list[tuple[int, int, list[str]]]:
    blocks: list[tuple[int, int, list[str]]] = []
    start: int | None = None
    current: list[str] = []
    current_kinds: list[Literal["hard", "soft"]] = []

    for index, line in enumerate(lines):
        row_kind = _table_row_kind(line)
        if row_kind:
            if start is None:
                start = index
            current.append(line)
            current_kinds.append(row_kind)
        else:
            if start is not None and _is_valid_table_block(current, current_kinds):
                blocks.append((start, index, current))
            start = None
            current = []
            current_kinds = []

    if start is not None and _is_valid_table_block(current, current_kinds):
        blocks.append((start, len(lines), current))

    return blocks


def _table_row_kind(line: str) -> Literal["hard", "soft"] | None:
    stripped = line.strip()
    if not stripped or _looks_like_list_item(stripped):
        return None
    if "|" in stripped and stripped.count("|") >= 2:
        return "hard"
    if re.search(r"\S\s{2,}\S|\t", line):
        return "hard"

    # After whitespace normalization, simple tables may only have single spaces.
    # Treat these as table candidates only when a later block-level check agrees.
    tokens = stripped.split()
    has_sentence_punctuation = bool(re.search(r"[.!?;:]", stripped))
    if 2 <= len(tokens) <= 6 and not has_sentence_punctuation:
        return "soft"
    return None


def _is_valid_table_block(lines: list[str], kinds: list[Literal["hard", "soft"]]) -> bool:
    if not lines:
        return False
    if "hard" in kinds:
        return len(lines) >= 2

    token_widths = [len(line.split()) for line in lines]
    if len(lines) < 3 or len(set(token_widths)) != 1:
        return False
    return token_widths[0] >= 2


def _split_columns(line: str) -> list[str]:
    stripped = line.strip()
    if "|" in stripped and stripped.count("|") >= 2:
        return [part.strip() for part in stripped.strip("|").split("|") if part.strip()]
    if re.search(r"\S\s{2,}\S|\t", line):
        return [part.strip() for part in re.split(r"\s{2,}|\t+", stripped) if part.strip()]
    return stripped.split()


def _convert_table_block(lines: list[str]) -> list[str]:
    rows = [_split_columns(line) for line in lines]
    rows = [row for row in rows if row]
    if len(rows) < 2:
        return []

    width_counts = Counter(len(row) for row in rows)
    expected_width = width_counts.most_common(1)[0][0]
    if expected_width < 2:
        return []

    rows = [_fit_row_width(row, expected_width) for row in rows]
    header, data_rows = rows[0], rows[1:]

    if expected_width == 2:
        return _convert_two_column_table(header, data_rows)

    return _convert_markdown_table(header, data_rows)


def _fit_row_width(row: list[str], width: int) -> list[str]:
    if len(row) == width:
        return row
    if len(row) > width:
        return row[: width - 1] + [" ".join(row[width - 1 :])]
    return row + [""] * (width - len(row))


def _convert_two_column_table(header: list[str], rows: list[list[str]]) -> list[str]:
    left_header, right_header = header
    converted: list[str] = []

    for row in rows:
        left_value, right_value = row
        if left_value:
            converted.append(f"{left_header}: {left_value}")
        if right_value:
            converted.append(f"{right_header}: {right_value}")
        if converted and converted[-1] != "":
            converted.append("")

    while converted and converted[-1] == "":
        converted.pop()
    return converted


def _convert_markdown_table(header: list[str], rows: list[list[str]]) -> list[str]:
    separator = ["---"] * len(header)
    table = [_markdown_row(header), _markdown_row(separator)]
    table.extend(_markdown_row(row) for row in rows)
    return table


def _markdown_row(values: Iterable[str]) -> str:
    escaped = [value.replace("|", "\\|").strip() for value in values]
    return "| " + " | ".join(escaped) + " |"


def _collapse_blank_lines(lines: list[str]) -> str:
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


if __name__ == "__main__":
    sample = """
Confidential
Page 1 of 3

Employee      Leave

Policy

Employees receive leave.

• Annual leave
  ◦ Carry forward rules
1) Sick leave
   a) Medical certificate required

Employee    Salary
John        50000
Jane        60000

@@@@@
"""

    cleaned_sample = preprocess_document(sample)
    headings = detect_headings(cleaned_sample)

    print(cleaned_sample)
    print()
    print("Headings:", headings)
