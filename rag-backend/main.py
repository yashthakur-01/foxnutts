"""Page-window PDF ingestion with topic-aware LangChain Document chunks."""

from __future__ import annotations

import argparse
import re
import shutil
import uuid
from pathlib import Path
from typing import Iterable, Literal, TypedDict

from langchain_core.documents import Document

import importlib

pdf_parsing = importlib.import_module("0_pdf_parsing")
preprocess_document = pdf_parsing.preprocess_document

markdown_parsing = importlib.import_module("0_markdown_parsing")
detect_markdown_headings = markdown_parsing.detect_markdown_headings
preprocess_markdown = markdown_parsing.preprocess_markdown
split_markdown_blocks = markdown_parsing.split_markdown_blocks


class QualityReport(TypedDict):
    """Quality metrics used to decide whether parsed text looks suspicious."""

    parser: str
    character_count: int
    word_count: int
    line_count: int
    heading_count: int
    table_line_count: int
    list_item_count: int
    suspicious_character_count: int
    suspicious_character_ratio: float
    alphanumeric_ratio: float
    average_line_length: float
    file_size_bytes: int
    page_count: int | None
    suspicious: bool
    reasons: list[str]


class PageWindowText(TypedDict):
    """Parsed text for a contiguous PDF page range."""

    text: str
    page_start: int
    page_end: int


class TextBlock(TypedDict):
    """A structure-aware text block used during chunking."""

    type: str
    text: str
    section_title: str


def main(
    pdf_path: str | Path,
    *,
    document_title: str = "",
    chunk_size_tokens: int = 300,
    chunk_overlap_tokens: int = 40,
    chars_per_token: float = 4.2,
    markitdown_pages_per_batch: int = 30,
    pymupdf_pages_per_window: int = 5,
) -> list[Document]:
    """Return page-aware, topic-aware chunks as LangChain ``Document`` objects.

    MarkItDown is tried first by converting temporary page-batch PDFs so page
    ranges can still be preserved. If that output looks suspicious, the
    fallback uses direct PyMuPDF page access with smaller page windows.
    """

    max_chars = max(1, int(chunk_size_tokens * chars_per_token))
    overlap_chars = max(0, int(chunk_overlap_tokens * chars_per_token))

    temp_path = Path.cwd() / f".rag_pdf_{uuid.uuid4().hex}"
    temp_path.mkdir(parents=True, exist_ok=False)
    try:
        source_path = _resolve_pdf_path(pdf_path)
        title = document_title.strip() or _title_from_path(source_path) or source_path.stem
        file_size = source_path.stat().st_size
        page_count = _get_pdf_page_count(source_path)

        try:
            markdown_windows = _parse_page_batches_with_markitdown(
                source_path,
                temp_path,
                pages_per_batch=markitdown_pages_per_batch,
            )
            markdown_text = "\n\n".join(window["text"] for window in markdown_windows)
            markdown_report = assess_parse_quality(
                markdown_text,
                parser="markitdown",
                file_size_bytes=file_size,
                page_count=page_count,
                markdown=True,
            )
            if not markdown_report["suspicious"]:
                return _windows_to_documents(
                    markdown_windows,
                    source_path=source_path,
                    document_title=title,
                    parser_name="markitdown",
                    markdown=True,
                    max_chars=max_chars,
                    overlap_chars=overlap_chars,
                    quality_report=markdown_report,
                    fallback_reason="",
                )
            fallback_reason = "; ".join(markdown_report["reasons"])
        except Exception as exc:
            fallback_reason = f"MarkItDown failed: {exc}"

        plain_windows = _parse_page_windows_with_pymupdf(
            source_path,
            pages_per_window=pymupdf_pages_per_window,
        )
        plain_text = "\n\n".join(window["text"] for window in plain_windows)
        report = assess_parse_quality(
            plain_text,
            parser="pymupdf",
            file_size_bytes=file_size,
            page_count=page_count,
            markdown=False,
        )
        return _windows_to_documents(
            plain_windows,
            source_path=source_path,
            document_title=title,
            parser_name="pymupdf",
            markdown=False,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
            quality_report=report,
            fallback_reason=fallback_reason,
        )
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


def assess_parse_quality(
    text: str,
    *,
    parser: str,
    file_size_bytes: int,
    page_count: int | None,
    markdown: bool,
) -> QualityReport:
    """Run lightweight quality checks over parsed text."""

    lines = text.splitlines()
    character_count = len(text)
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)
    line_count = len(lines)
    suspicious_character_count = len(re.findall(r"[\ufffd\u25a1]|[@%#]{5,}", text))
    alnum_count = sum(1 for char in text if char.isalnum())
    non_space_count = sum(1 for char in text if not char.isspace())

    heading_count = (
        len(detect_markdown_headings(text)) if markdown else len(_detect_plain_headings(text))
    )
    table_line_count = sum(1 for line in lines if _looks_like_markdown_table_line(line))
    list_item_count = sum(1 for line in lines if _looks_like_list_item(line.strip()))
    suspicious_ratio = suspicious_character_count / max(character_count, 1)
    alphanumeric_ratio = alnum_count / max(non_space_count, 1)
    average_line_length = character_count / max(line_count, 1)

    reasons: list[str] = []
    if character_count < 500:
        reasons.append("very low character count")
    if file_size_bytes >= 100_000 and character_count < 2_000:
        reasons.append("large PDF produced very little text")
    if page_count and page_count >= 5 and character_count / page_count < 250:
        reasons.append("low text density per page")
    if word_count < 100 and file_size_bytes >= 100_000:
        reasons.append("very low word count for PDF size")
    if suspicious_ratio > 0.02:
        reasons.append("too many OCR replacement or junk characters")
    if character_count >= 500 and alphanumeric_ratio < 0.45:
        reasons.append("low alphanumeric ratio")
    if page_count and page_count >= 3 and heading_count == 0 and markdown:
        reasons.append("no headings detected in multi-page Markdown parse")

    return {
        "parser": parser,
        "character_count": character_count,
        "word_count": word_count,
        "line_count": line_count,
        "heading_count": heading_count,
        "table_line_count": table_line_count,
        "list_item_count": list_item_count,
        "suspicious_character_count": suspicious_character_count,
        "suspicious_character_ratio": round(suspicious_ratio, 4),
        "alphanumeric_ratio": round(alphanumeric_ratio, 4),
        "average_line_length": round(average_line_length, 2),
        "file_size_bytes": file_size_bytes,
        "page_count": page_count,
        "suspicious": bool(reasons),
        "reasons": reasons,
    }


def chunk_plain_text_by_structure(
    text: str,
    *,
    document_title: str = "",
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> list[str]:
    """Backward-compatible string chunking for cleaned plain text."""

    blocks = _split_plain_text_blocks(text)
    chunks = _chunk_blocks_by_topic(
        blocks,
        document_title=document_title,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )
    return [chunk_text for chunk_text, _section in chunks]


def _windows_to_documents(
    windows: list[PageWindowText],
    *,
    source_path: Path,
    document_title: str,
    parser_name: str,
    markdown: bool,
    max_chars: int,
    overlap_chars: int,
    quality_report: QualityReport,
    fallback_reason: str,
) -> list[Document]:
    documents: list[Document] = []

    for window_index, window in enumerate(windows, start=1):
        cleaned = preprocess_markdown(window["text"]) if markdown else preprocess_document(window["text"])
        blocks = _markdown_blocks(cleaned) if markdown else _split_plain_text_blocks(cleaned)
        chunk_pairs = _chunk_blocks_by_topic(
            blocks,
            document_title=document_title,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
        )

        for chunk_index, (chunk_text, section_title) in enumerate(chunk_pairs, start=1):
            metadata = {
                "source": str(source_path),
                "document_title": document_title,
                "section_title": section_title,
                "page": window["page_start"],
                "page_start": window["page_start"],
                "page_end": window["page_end"],
                "page_window": f"{window['page_start']}-{window['page_end']}",
                "window_index": window_index,
                "chunk_index": chunk_index,
                "parser": parser_name,
                "fallback_reason": fallback_reason,
                "chunk_size_chars": len(chunk_text),
                "chunk_size_tokens_estimate": max(1, round(len(chunk_text) / 4.2)),
                "quality_suspicious": quality_report["suspicious"],
                "quality_reasons": quality_report["reasons"],
            }
            documents.append(Document(page_content=chunk_text, metadata=metadata))

    return documents


def _chunk_blocks_by_topic(
    blocks: list[TextBlock],
    *,
    document_title: str,
    max_chars: int,
    overlap_chars: int,
) -> list[tuple[str, str]]:
    topic_groups = _group_blocks_by_heading(blocks)
    chunks: list[tuple[str, str]] = []

    for section_title, topic_blocks in topic_groups:
        current: list[str] = []
        previous_overlap = ""

        for block in topic_blocks:
            block_text = block["text"].strip()
            if not block_text:
                continue

            candidate_parts = ([previous_overlap] if previous_overlap else []) + current + [block_text]
            candidate = "\n\n".join(part for part in candidate_parts if part).strip()

            if current and len(candidate) > max_chars:
                chunk_text = _with_context(
                    "\n\n".join(([previous_overlap] if previous_overlap else []) + current),
                    document_title,
                    section_title,
                )
                chunks.append((chunk_text, section_title))
                previous_overlap = _tail_overlap("\n\n".join(current), overlap_chars)
                current = []

            if len(block_text) > max_chars and block["type"] not in {"table", "list", "code"}:
                for part in _split_long_text(block_text, max_chars, overlap_chars):
                    chunk_text = _with_context(
                        "\n\n".join(part for part in [previous_overlap, part] if part),
                        document_title,
                        section_title,
                    )
                    chunks.append((chunk_text, section_title))
                    previous_overlap = _tail_overlap(part, overlap_chars)
            else:
                current.append(block_text)

        if current:
            chunk_text = _with_context(
                "\n\n".join(([previous_overlap] if previous_overlap else []) + current),
                document_title,
                section_title,
            )
            chunks.append((chunk_text, section_title))

    return chunks


def _group_blocks_by_heading(blocks: list[TextBlock]) -> list[tuple[str, list[TextBlock]]]:
    groups: list[tuple[str, list[TextBlock]]] = []
    current_section = ""
    current_blocks: list[TextBlock] = []

    for block in blocks:
        if block["type"] == "heading":
            if current_blocks:
                groups.append((current_section, current_blocks))
            current_section = block["section_title"] or _strip_heading_markup(block["text"])
            current_blocks = [block]
            continue
        current_blocks.append(block)

    if current_blocks:
        groups.append((current_section, current_blocks))

    return groups


def _markdown_blocks(markdown: str) -> list[TextBlock]:
    return [
        {
            "type": block["type"],
            "text": block["text"],
            "section_title": block["section_title"],
        }
        for block in split_markdown_blocks(markdown)
    ]


def _resolve_pdf_path(pdf_path: str | Path) -> Path:
    source = Path(pdf_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"PDF not found: {source}")
    if not source.is_file():
        raise ValueError(f"Expected a file, got: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {source}")
    return source


def _parse_page_batches_with_markitdown(
    pdf_path: Path,
    temp_dir: Path,
    *,
    pages_per_batch: int,
) -> list[PageWindowText]:
    """Parse temporary page-batch PDFs with MarkItDown and keep page ranges."""

    page_count = _require_pdf_page_count(pdf_path)
    windows: list[PageWindowText] = []

    for page_start, page_end in _iter_page_windows(page_count, pages_per_batch):
        batch_pdf = _write_pdf_page_batch(pdf_path, temp_dir, page_start, page_end)
        text = _parse_with_markitdown(batch_pdf).strip()
        if text:
            windows.append({"text": text, "page_start": page_start, "page_end": page_end})

    if not windows:
        raise ValueError("MarkItDown returned no text for all page batches")
    return windows


def _parse_page_windows_with_pymupdf(
    pdf_path: Path,
    *,
    pages_per_window: int,
) -> list[PageWindowText]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Install PyMuPDF to use the fallback parser") from exc

    windows: list[PageWindowText] = []
    with fitz.open(str(pdf_path)) as document:
        for page_start, page_end in _iter_page_windows(document.page_count, pages_per_window):
            parts: list[str] = []
            for page_number in range(page_start, page_end + 1):
                page = document[page_number - 1]
                text = page.get_text("text").strip()
                if text:
                    parts.append(f"Page {page_number}\n{text}")
            if parts:
                windows.append(
                    {
                        "text": "\n\n".join(parts),
                        "page_start": page_start,
                        "page_end": page_end,
                    }
                )
    return windows


def _write_pdf_page_batch(
    pdf_path: Path,
    temp_dir: Path,
    page_start: int,
    page_end: int,
) -> Path:
    """Write a temporary PDF containing one page batch for MarkItDown."""

    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Install PyMuPDF to create MarkItDown page batches") from exc

    output_path = temp_dir / f"{pdf_path.stem}_pages_{page_start}_{page_end}.pdf"
    with fitz.open(str(pdf_path)) as source:
        with fitz.open() as target:
            target.insert_pdf(source, from_page=page_start - 1, to_page=page_end - 1)
            output_path.write_bytes(target.tobytes())
    return output_path


def _iter_page_windows(page_count: int, pages_per_window: int) -> Iterable[tuple[int, int]]:
    window_size = max(1, pages_per_window)
    for page_start in range(1, page_count + 1, window_size):
        page_end = min(page_start + window_size - 1, page_count)
        yield page_start, page_end


def _get_pdf_page_count(pdf_path: Path) -> int | None:
    try:
        import fitz
    except ImportError:
        return None

    try:
        with fitz.open(str(pdf_path)) as document:
            return int(document.page_count)
    except Exception:
        return None


def _require_pdf_page_count(pdf_path: Path) -> int:
    page_count = _get_pdf_page_count(pdf_path)
    if not page_count:
        raise RuntimeError("Could not determine PDF page count")
    return page_count


def _parse_with_markitdown(pdf_path: Path) -> str:
    try:
        # pyrefly: ignore [missing-import]
        from markitdown import MarkItDown
    except ImportError as exc:
        raise RuntimeError("Install markitdown to use the Markdown parser") from exc

    converter = MarkItDown()
    result = converter.convert(str(pdf_path))
    text = getattr(result, "text_content", "")
    if not text:
        raise ValueError("MarkItDown returned empty text")
    return str(text)


def _title_from_path(pdf_path: Path) -> str:
    name = pdf_path.stem
    return re.sub(r"[-_]+", " ", name).strip().title()


def _split_plain_text_blocks(text: str) -> list[TextBlock]:
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]
    blocks: list[TextBlock] = []
    current_section = ""

    for paragraph in paragraphs:
        lines = paragraph.splitlines()
        block_type: Literal["heading", "paragraph", "list", "table"]
        if all(_looks_like_list_item(line.strip()) or line.startswith((" ", "\t")) for line in lines):
            block_type = "list"
        elif all(_looks_like_key_value_line(line) for line in lines) and len(lines) >= 2:
            block_type = "table"
        elif len(lines) == 1 and _detect_plain_headings(paragraph):
            block_type = "heading"
            current_section = paragraph.strip()
        else:
            block_type = "paragraph"

        blocks.append(
            {
                "type": block_type,
                "text": paragraph,
                "section_title": current_section,
            }
        )

    return blocks


def _detect_plain_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 100:
            continue
        words = stripped.split()
        if len(words) <= 12 and (
            stripped.isupper()
            or stripped.endswith(":")
            or sum(1 for word in words if word[:1].isupper()) / max(len(words), 1) >= 0.8
        ):
            headings.append(stripped)
    return headings


def _looks_like_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    return "|" in stripped and stripped.count("|") >= 1


def _looks_like_list_item(line: str) -> bool:
    return bool(
        re.match(
            r"^(\s*)((?:[-*+])|(?:\d+[\.)])|(?:[A-Za-z][\.)])|(?:[ivxlcdmIVXLCDM]+[\.)]))\s+",
            line,
        )
    )


def _looks_like_key_value_line(line: str) -> bool:
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9 /_-]{0,40}:\s+\S+", line.strip()))


def _strip_heading_markup(text: str) -> str:
    stripped = text.strip()
    markdown_heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", stripped)
    return markdown_heading.group(1).strip() if markdown_heading else stripped


def _with_context(text: str, document_title: str, section_title: str) -> str:
    metadata: list[str] = []
    if document_title.strip():
        metadata.append(f"Document Title: {document_title.strip()}")
    if section_title.strip():
        metadata.append(f"Section Title: {section_title.strip()}")
    return "\n".join(metadata + ["", text.strip()]).strip() if metadata else text.strip()


def _tail_overlap(text: str, overlap_chars: int) -> str:
    if overlap_chars <= 0:
        return ""
    return _trim_to_boundary(text.strip()[-overlap_chars:])


def _split_long_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            boundary_end = _find_boundary_end(text, start, end)
            if boundary_end is not None and boundary_end > start + max_chars // 2:
                end = boundary_end
        chunk = _trim_to_boundary(text[start:end])
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(_boundary_overlap_start(text, end, overlap_chars), start + 1)
    return chunks


def _find_boundary_end(text: str, start: int, end: int) -> int | None:
    window = text[start:end]
    paragraph_break = window.rfind("\n\n")
    sentence_breaks = [
        window.rfind(". "),
        window.rfind("! "),
        window.rfind("? "),
    ]
    sentence_break = max(sentence_breaks)

    if paragraph_break >= 0:
        return start + paragraph_break + 2
    if sentence_break >= 0:
        return start + sentence_break + 2
    single_newline = window.rfind("\n")
    if single_newline >= 0:
        return start + single_newline + 1
    return None


def _boundary_overlap_start(text: str, end: int, overlap_chars: int) -> int:
    if overlap_chars <= 0:
        return end

    start = max(0, end - overlap_chars)
    overlap_text = text[start:end].lstrip()

    sentence_start = _find_sentence_start(overlap_text)
    if sentence_start is not None:
        return start + sentence_start

    paragraph_start = overlap_text.rfind("\n\n")
    if paragraph_start >= 0:
        return start + paragraph_start + 2

    line_start = overlap_text.rfind("\n")
    if line_start >= 0:
        return start + line_start + 1

    return start


def _find_sentence_start(text: str) -> int | None:
    for separator in (". ", "! ", "? "):
        position = text.rfind(separator)
        if position >= 0:
            return position + 2
    return None


def _trim_to_boundary(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""

    paragraph_break = stripped.rfind("\n\n")
    if paragraph_break >= 0 and paragraph_break >= len(stripped) * 0.5:
        return stripped[: paragraph_break + 2].strip()

    sentence_break = max(stripped.rfind(". "), stripped.rfind("! "), stripped.rfind("? "))
    if sentence_break >= 0 and sentence_break >= len(stripped) * 0.5:
        return stripped[: sentence_break + 1].strip()

    newline_break = stripped.rfind("\n")
    if newline_break >= 0 and newline_break >= len(stripped) * 0.5:
        return stripped[: newline_break + 1].strip()

    return stripped


def _print_documents_summary(documents: list[Document]) -> None:
    parser_name = documents[0].metadata.get("parser", "") if documents else ""
    fallback_reason = documents[0].metadata.get("fallback_reason", "") if documents else ""
    print(f"Parser used: {parser_name}")
    if fallback_reason:
        print(f"Fallback reason: {fallback_reason}")
    print(f"Documents/chunks: {len(documents)}")
    if documents:
        page_start = min(int(doc.metadata["page_start"]) for doc in documents)
        page_end = max(int(doc.metadata["page_end"]) for doc in documents)
        print(f"Page range: {page_start}-{page_end}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse a local PDF file into LangChain Documents.")
    parser.add_argument("pdf_path", help="Local PDF file path to ingest")
    parser.add_argument("--title", default="", help="Document title to add to chunk context")
    parser.add_argument("--chunk-size-tokens", type=int, default=300)
    parser.add_argument("--chunk-overlap-tokens", type=int, default=40)
    parser.add_argument("--chars-per-token", type=float, default=4.2)
    parser.add_argument("--markitdown-pages-per-batch", type=int, default=30)
    parser.add_argument("--pymupdf-pages-per-window", type=int, default=5)
    parser.add_argument("--output", default="", help="Optional path to write chunks as text")
    args = parser.parse_args()

    docs = main(
        args.pdf_path,
        document_title=args.title,
        chunk_size_tokens=args.chunk_size_tokens,
        chunk_overlap_tokens=args.chunk_overlap_tokens,
        chars_per_token=args.chars_per_token,
        markitdown_pages_per_batch=args.markitdown_pages_per_batch,
        pymupdf_pages_per_window=args.pymupdf_pages_per_window,
    )
    _print_documents_summary(docs)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            "\n\n--- CHUNK ---\n\n".join(doc.page_content for doc in docs),
            encoding="utf-8",
        )
        print(f"Wrote chunks to: {output_path}")

