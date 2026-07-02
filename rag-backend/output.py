"""Print parsed document content from a local PDF file."""

from __future__ import annotations

import argparse
from pathlib import Path

from main import main as parse_document


def print_document_content(
    pdf_path: str,
    *,
    title: str = "",
    output_file: str = "outputFile.txt",
    chunk_size_tokens: int = 300,
    chunk_overlap_tokens: int = 40,
) -> None:
    """Parse a local PDF file and write each chunk to a text file."""

    documents = parse_document(
        pdf_path,
        document_title=title,
        chunk_size_tokens=chunk_size_tokens,
        chunk_overlap_tokens=chunk_overlap_tokens,
    )
    output_path = Path(output_file)

    lines: list[str] = [f"Chunks: {len(documents)}"]

    for index, document in enumerate(documents, start=1):
        lines.append(f"\n--- CHUNK {index} ---\n")
        lines.append(document.page_content)

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(documents)} chunks to {output_path.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Write parsed content from a local PDF file to outputFile.txt.")
    parser.add_argument("pdf_path", help="Local PDF file path to parse")
    parser.add_argument("--title", default="", help="Optional document title")
    parser.add_argument("--output-file", default="outputFile.txt", help="Output text file path")
    parser.add_argument("--chunk-size-tokens", type=int, default=300, help="Chunk size in tokens")
    parser.add_argument("--chunk-overlap-tokens", type=int, default=40, help="Chunk overlap in tokens")
    args = parser.parse_args()

    print_document_content(
        args.pdf_path,
        title=args.title,
        output_file=args.output_file,
        chunk_size_tokens=args.chunk_size_tokens,
        chunk_overlap_tokens=args.chunk_overlap_tokens,
    )