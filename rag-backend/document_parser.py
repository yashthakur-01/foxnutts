"""Document parsing utilities for converting source files to Markdown.

The pipeline is built on Docling and is intentionally small:
- pass one file to ``convert_document_to_markdown``
- pass many files to ``convert_documents_to_markdown``
- pass a file or directory to ``convert_path_to_markdown``

When an output directory is provided, converted Markdown files are written with
the same stem as the source document.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.base_models import FormatToExtensions
from docling.document_converter import DocumentConverter


ALLOWED_INPUT_FORMATS = [
    InputFormat.ASCIIDOC,
    InputFormat.CSV,
    InputFormat.DOCX,
    InputFormat.HTML,
    InputFormat.IMAGE,
    InputFormat.JSON_DOCLING,
    InputFormat.LATEX,
    InputFormat.MD,
    InputFormat.PDF,
    InputFormat.PPTX,
    InputFormat.VTT,
    InputFormat.XLSX,
    InputFormat.XML_JATS,
    InputFormat.XML_USPTO,
    InputFormat.XML_XBRL,
]

SUPPORTED_EXTENSIONS = {
    f".{extension.lower()}"
    for input_format in ALLOWED_INPUT_FORMATS
    for extension in FormatToExtensions[input_format]
}


@dataclass(frozen=True)
class MarkdownConversion:
    """Result for one source document converted by Docling."""

    source_path: Path
    markdown: str
    output_path: Path | None
    status: ConversionStatus
    errors: tuple[str, ...] = ()


def create_docling_converter() -> DocumentConverter:
    """Create a Docling converter for common RAG ingestion formats."""

    return DocumentConverter(allowed_formats=ALLOWED_INPUT_FORMATS)


def convert_document_to_markdown(
    source_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    converter: DocumentConverter | None = None,
    max_num_pages: int | None = None,
    max_file_size: int | None = None,
) -> MarkdownConversion:
    """Convert a single PDF, DOCX, PPTX, image, sheet, or text file to Markdown.

    Args:
        source_path: Path to the source document.
        output_dir: Optional directory where a ``.md`` file should be written.
        converter: Optional shared Docling converter. Reuse this for batches.
        max_num_pages: Optional page limit for supported formats.
        max_file_size: Optional byte-size limit enforced by Docling.

    Returns:
        A ``MarkdownConversion`` containing Markdown text and optional file path.

    Raises:
        FileNotFoundError: If ``source_path`` does not exist.
        ValueError: If ``source_path`` is not a file.
        RuntimeError: If Docling fails or partially fails the conversion.
    """

    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Document not found: {source}")
    if not source.is_file():
        raise ValueError(f"Expected a file, got: {source}")

    doc_converter = converter or create_docling_converter()
    convert_kwargs: dict[str, int] = {}
    if max_num_pages is not None:
        convert_kwargs["max_num_pages"] = max_num_pages
    if max_file_size is not None:
        convert_kwargs["max_file_size"] = max_file_size

    result = doc_converter.convert(source, **convert_kwargs)
    errors = tuple(str(error) for error in result.errors)

    if result.status not in {
        ConversionStatus.SUCCESS,
        ConversionStatus.PARTIAL_SUCCESS,
    }:
        message = "; ".join(errors) if errors else result.status.value
        raise RuntimeError(f"Failed to convert {source}: {message}")

    markdown = result.document.export_to_markdown()
    output_path = _write_markdown(source, markdown, output_dir) if output_dir else None

    return MarkdownConversion(
        source_path=source,
        markdown=markdown,
        output_path=output_path,
        status=result.status,
        errors=errors,
    )


def convert_documents_to_markdown(
    source_paths: Iterable[str | Path],
    output_dir: str | Path | None = None,
    *,
    max_num_pages: int | None = None,
    max_file_size: int | None = None,
) -> list[MarkdownConversion]:
    """Convert many source files to Markdown using one shared Docling converter."""

    converter = create_docling_converter()
    return [
        convert_document_to_markdown(
            source_path,
            output_dir,
            converter=converter,
            max_num_pages=max_num_pages,
            max_file_size=max_file_size,
        )
        for source_path in source_paths
    ]


def convert_path_to_markdown(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    *,
    recursive: bool = True,
    max_num_pages: int | None = None,
    max_file_size: int | None = None,
) -> list[MarkdownConversion]:
    """Convert a file or every supported document in a directory to Markdown."""

    path = Path(input_path).expanduser().resolve()
    if path.is_file():
        return [
            convert_document_to_markdown(
                path,
                output_dir,
                max_num_pages=max_num_pages,
                max_file_size=max_file_size,
            )
        ]
    if not path.is_dir():
        raise FileNotFoundError(f"Input path not found: {path}")

    pattern = "**/*" if recursive else "*"
    sources = sorted(
        child
        for child in path.glob(pattern)
        if child.is_file() and child.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    return convert_documents_to_markdown(
        sources,
        output_dir,
        max_num_pages=max_num_pages,
        max_file_size=max_file_size,
    )


def _write_markdown(
    source_path: Path,
    markdown: str,
    output_dir: str | Path,
) -> Path:
    destination_dir = Path(output_dir).expanduser().resolve()
    destination_dir.mkdir(parents=True, exist_ok=True)

    destination = destination_dir / f"{source_path.stem}.md"
    destination.write_text(markdown, encoding="utf-8")
    return destination


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert PDFs, Office docs, images, and other documents to Markdown."
    )
    parser.add_argument("input_path", help="File or directory to convert.")
    parser.add_argument(
        "-o",
        "--output-dir",
        default="markdown_output",
        help="Directory for generated Markdown files.",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only scan the top-level directory when input_path is a directory.",
    )
    args = parser.parse_args()

    conversions = convert_path_to_markdown(
        args.input_path,
        args.output_dir,
        recursive=not args.no_recursive,
    )
    for conversion in conversions:
        print(f"{conversion.source_path} -> {conversion.output_path}")
