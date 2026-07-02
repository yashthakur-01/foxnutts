"""Optimized Docling PDF parsing with a no-OCR quality gate and Celery fan-out.

This module is designed for PDFs that already contain selectable text. It first
samples a small number of pages with lightweight PDF text extraction, checks
whether the extracted text looks healthy, and only then parses the full document
with Docling and OCR disabled.

Run a worker with:
    celery -A document_parser2.celery_app worker --loglevel=info

Redis defaults to:
    redis://localhost:6379/0
"""

from __future__ import annotations

import math
import os
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import pypdfium2 as pdfium
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

try:
    from celery import Celery, group
except ImportError:  # pragma: no cover - depends on deployment environment.
    Celery = None
    group = None


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEFAULT_CHUNK_SIZE = int(os.getenv("DOCLING_PAGE_CHUNK_SIZE", "5"))
IMAGE_PLACEHOLDER_RE = re.compile(r"<!--\s*image\s*-->", re.IGNORECASE)


if Celery is not None:
    celery_app = Celery(
        "document_parser2",
        broker=REDIS_URL,
        backend=REDIS_URL,
    )
    celery_app.conf.update(
        task_track_started=True,
        worker_prefetch_multiplier=1,
        task_acks_late=True,
    )
else:
    celery_app = None


@dataclass(frozen=True)
class TextQualityMetrics:
    text_length: int
    word_count: int
    page_count: int
    alphanumeric_ratio: float
    whitespace_ratio: float
    word_density: float
    repeated_symbol_ratio: float
    max_repeated_symbol_run: int
    is_good: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ParseResult:
    source_path: Path
    output_path: Path | None
    page_count: int
    sampled_pages: tuple[int, ...]
    quality: TextQualityMetrics
    markdown: str


def create_no_ocr_pdf_converter() -> DocumentConverter:
    """Create a Docling PDF converter tuned for text-backed PDFs."""

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.force_backend_text = True
    options.generate_page_images = False
    options.generate_picture_images = False
    options.generate_table_images = False
    options.do_picture_classification = False
    options.do_picture_description = False
    options.do_chart_extraction = False
    options.ocr_batch_size = 1
    options.layout_batch_size = 1
    options.table_batch_size = 1
    options.queue_max_size = 1

    return DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        },
    )


def get_pdf_page_count(pdf_path: str | Path) -> int:
    """Return the number of pages in a PDF without running Docling."""

    source = Path(pdf_path).expanduser().resolve()
    with pdfium.PdfDocument(str(source)) as pdf:
        return len(pdf)


def select_sample_pages(
    total_pages: int,
    *,
    ratio: float = 0.10,
    max_pages: int = 10,
    seed: int | None = None,
) -> tuple[int, ...]:
    """Randomly select up to 10% of pages, capped at ``max_pages``."""

    if total_pages < 1:
        return ()

    sample_count = min(max_pages, max(1, math.ceil(total_pages * ratio)))
    rng = random.Random(seed)
    return tuple(sorted(rng.sample(range(1, total_pages + 1), sample_count)))


def evaluate_text_quality(
    text: str,
    *,
    page_count: int,
    min_chars_per_page: int = 150,
    min_alphanumeric_ratio: float = 0.45,
    max_whitespace_ratio: float = 0.45,
    min_words_per_page: float = 25.0,
    max_repeated_symbol_ratio: float = 0.02,
    max_repeated_symbol_run: int = 20,
) -> TextQualityMetrics:
    """Score whether extracted text is usable enough to skip OCR."""

    text_length = len(text)
    page_count = max(page_count, 1)
    alphanumeric_count = sum(char.isalnum() for char in text)
    whitespace_count = sum(char.isspace() for char in text)
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-']*", text)

    repeated_symbol_chars = sum(
        len(match.group(0))
        for match in re.finditer(r"([^\w\s])\1{2,}", text)
    )
    repeated_runs = [len(match.group(0)) for match in re.finditer(r"([^\w\s])\1{2,}", text)]

    alphanumeric_ratio = alphanumeric_count / text_length if text_length else 0.0
    whitespace_ratio = whitespace_count / text_length if text_length else 1.0
    word_density = len(words) / page_count
    repeated_symbol_ratio = repeated_symbol_chars / text_length if text_length else 0.0
    longest_symbol_run = max(repeated_runs, default=0)

    reasons: list[str] = []
    if text_length < min_chars_per_page * page_count:
        reasons.append("too little extracted text")
    if alphanumeric_ratio < min_alphanumeric_ratio:
        reasons.append("low alphanumeric ratio")
    if whitespace_ratio > max_whitespace_ratio:
        reasons.append("high whitespace ratio")
    if word_density < min_words_per_page:
        reasons.append("low word density")
    if repeated_symbol_ratio > max_repeated_symbol_ratio:
        reasons.append("too many repeated symbols")
    if longest_symbol_run > max_repeated_symbol_run:
        reasons.append("single repeated-symbol run is too long")

    return TextQualityMetrics(
        text_length=text_length,
        word_count=len(words),
        page_count=page_count,
        alphanumeric_ratio=round(alphanumeric_ratio, 4),
        whitespace_ratio=round(whitespace_ratio, 4),
        word_density=round(word_density, 2),
        repeated_symbol_ratio=round(repeated_symbol_ratio, 4),
        max_repeated_symbol_run=longest_symbol_run,
        is_good=not reasons,
        reasons=tuple(reasons),
    )


def convert_pdf_page_range_without_ocr(
    pdf_path: str | Path,
    start_page: int,
    end_page: int,
    *,
    fallback_to_pdf_text: bool = True,
) -> str:
    """Convert an inclusive PDF page range to Markdown with OCR disabled."""

    source = Path(pdf_path).expanduser().resolve()
    converter = create_no_ocr_pdf_converter()
    result = converter.convert(source, page_range=(start_page, end_page))

    if result.status not in {
        ConversionStatus.SUCCESS,
        ConversionStatus.PARTIAL_SUCCESS,
    }:
        errors = "; ".join(str(error) for error in result.errors)
        raise RuntimeError(
            f"Docling failed on pages {start_page}-{end_page}: "
            f"{errors or result.status.value}"
        )

    markdown = result.document.export_to_markdown()
    if fallback_to_pdf_text and not is_usable_markdown(markdown, end_page - start_page + 1):
        return extract_pdf_text_page_range_as_markdown(source, start_page, end_page)

    return markdown


def is_usable_markdown(markdown: str, page_count: int) -> bool:
    """Return whether Docling Markdown contains meaningful text, not placeholders."""

    text_without_images = IMAGE_PLACEHOLDER_RE.sub("", markdown).strip()
    if not text_without_images:
        return False

    quality = evaluate_text_quality(
        text_without_images,
        page_count=page_count,
        min_chars_per_page=80,
        min_words_per_page=12.0,
    )
    return quality.is_good


def extract_pdf_text_page_range_as_markdown(
    pdf_path: str | Path,
    start_page: int,
    end_page: int,
) -> str:
    """Extract selectable PDF text for a page range and format it as Markdown."""

    source = Path(pdf_path).expanduser().resolve()
    chunks: list[str] = []
    with pdfium.PdfDocument(str(source)) as pdf:
        for page_number in range(start_page, end_page + 1):
            page = pdf[page_number - 1]
            text_page = page.get_textpage()
            try:
                text = text_page.get_text_range().strip()
            finally:
                text_page.close()
                page.close()

            if text:
                chunks.append(f"<!-- page {page_number} -->\n\n{normalize_pdf_text(text)}")

    return "\n\n".join(chunks)


def normalize_pdf_text(text: str) -> str:
    """Clean PDF text extraction output enough for RAG-friendly Markdown."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_sample_text_without_ocr(
    pdf_path: str | Path,
    sampled_pages: Iterable[int],
) -> str:
    """Extract sampled page text quickly without OCR or Docling model loading."""

    source = Path(pdf_path).expanduser().resolve()
    chunks: list[str] = []
    with pdfium.PdfDocument(str(source)) as pdf:
        for page_number in sampled_pages:
            page = pdf[page_number - 1]
            text_page = page.get_textpage()
            try:
                chunks.append(text_page.get_text_range())
            finally:
                text_page.close()
                page.close()
    return "\n\n".join(chunks)


def build_page_ranges(total_pages: int, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[tuple[int, int]]:
    """Split a PDF into inclusive page ranges for distributed parsing."""

    if total_pages < 1:
        return []
    if chunk_size < 1:
        raise ValueError("chunk_size must be greater than zero")

    return [
        (start, min(start + chunk_size - 1, total_pages))
        for start in range(1, total_pages + 1, chunk_size)
    ]


def parse_pdf_without_ocr_sync(
    pdf_path: str | Path,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Parse the full PDF text layer locally in small chunks without OCR."""

    total_pages = get_pdf_page_count(pdf_path)
    chunks = build_page_ranges(total_pages, chunk_size)
    return "\n\n".join(
        extract_pdf_text_page_range_as_markdown(pdf_path, start, end)
        for start, end in chunks
    )


def parse_pdf_without_ocr_distributed(
    pdf_path: str | Path,
    *,
    total_pages: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    timeout: int | None = None,
) -> str:
    """Parse the full PDF text layer through Celery workers."""

    if celery_app is None or group is None:
        raise RuntimeError("Celery is not installed. Install celery and redis first.")

    chunks = build_page_ranges(total_pages, chunk_size)
    job = group(
        extract_pdf_text_page_range_task.s(str(Path(pdf_path).expanduser().resolve()), start, end)
        for start, end in chunks
    )
    results = job.apply_async().get(timeout=timeout)
    ordered_results = sorted(results, key=lambda item: item["start_page"])
    return "\n\n".join(item["markdown"] for item in ordered_results)


def parse_pdf_with_quality_gate(
    pdf_path: str | Path,
    output_path: str | Path | None = None,
    *,
    sample_ratio: float = 0.10,
    max_sample_pages: int = 10,
    sample_seed: int | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    use_celery: bool = True,
    celery_timeout: int | None = None,
) -> ParseResult:
    """Sample a PDF, validate text quality, then parse all pages without OCR.

    If the sampled text looks poor, this raises ``RuntimeError`` instead of
    falling back to OCR. That keeps expensive OCR explicit.
    """

    source = Path(pdf_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"PDF not found: {source}")
    if source.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {source}")

    total_pages = get_pdf_page_count(source)
    sampled_pages = select_sample_pages(
        total_pages,
        ratio=sample_ratio,
        max_pages=max_sample_pages,
        seed=sample_seed,
    )
    sample_text = extract_sample_text_without_ocr(source, sampled_pages)
    quality = evaluate_text_quality(sample_text, page_count=len(sampled_pages))

    if not quality.is_good:
        raise RuntimeError(
            "No-OCR extraction quality check failed: "
            f"{', '.join(quality.reasons)}. Metrics: {asdict(quality)}"
        )

    if use_celery:
        markdown = parse_pdf_without_ocr_distributed(
            source,
            total_pages=total_pages,
            chunk_size=chunk_size,
            timeout=celery_timeout,
        )
    else:
        markdown = parse_pdf_without_ocr_sync(source, chunk_size=chunk_size)

    destination = None
    if output_path is not None:
        destination = Path(output_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(markdown, encoding="utf-8")

    return ParseResult(
        source_path=source,
        output_path=destination,
        page_count=total_pages,
        sampled_pages=sampled_pages,
        quality=quality,
        markdown=markdown,
    )


if celery_app is not None:

    @celery_app.task(name="document_parser2.convert_pdf_page_range")
    def convert_pdf_page_range_task(
        pdf_path: str,
        start_page: int,
        end_page: int,
    ) -> dict[str, Any]:
        markdown = convert_pdf_page_range_without_ocr(pdf_path, start_page, end_page)
        return {
            "pdf_path": pdf_path,
            "start_page": start_page,
            "end_page": end_page,
            "markdown": markdown,
        }

    @celery_app.task(name="document_parser2.extract_pdf_text_page_range")
    def extract_pdf_text_page_range_task(
        pdf_path: str,
        start_page: int,
        end_page: int,
    ) -> dict[str, Any]:
        markdown = extract_pdf_text_page_range_as_markdown(pdf_path, start_page, end_page)
        return {
            "pdf_path": pdf_path,
            "start_page": start_page,
            "end_page": end_page,
            "markdown": markdown,
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Parse a text-backed PDF with Docling, sampling first and skipping OCR."
    )
    parser.add_argument("pdf_path")
    parser.add_argument("-o", "--output-path")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--sample-seed", type=int)
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Run locally without Celery. Useful for smoke tests.",
    )
    args = parser.parse_args()

    parsed = parse_pdf_with_quality_gate(
        args.pdf_path,
        args.output_path,
        sample_seed=args.sample_seed,
        chunk_size=args.chunk_size,
        use_celery=not args.sync,
    )
    print(f"Parsed {parsed.page_count} pages.")
    print(f"Sampled pages: {parsed.sampled_pages}")
    print(f"Quality: {asdict(parsed.quality)}")
    if parsed.output_path:
        print(f"Wrote Markdown to: {parsed.output_path}")
