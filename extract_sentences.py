#!/usr/bin/env python3
"""Extract sentence segments from PDF or UTF-8 text with min/max word constraints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import os

from src.sentence_extractor import DEFAULT_SOFT_DELIMITERS
from src.sentence_extractor import chunk_sentences
from src.sentence_extractor import extract_chapter_names_from_toc_pdf
from src.sentence_extractor import extract_sentences_from_path
from src.sentence_extractor import write_chunked_sentences_output
from src.sentence_extractor import write_sentences_output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract text from a PDF or TXT file and split into sentence segments "
            "with target word lengths in [min_length, max_length]."
        )
    )
    parser.add_argument("input_path", type=Path, help="Path to .pdf or .txt input")
    parser.add_argument("--output", type=Path, default=None, help="Optional output file (.txt or .json)")
    parser.add_argument("--min-length", type=int, default=5, help="Minimum words per sentence segment")
    parser.add_argument("--max-length", type=int, default=25, help="Maximum words per sentence segment")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=0,
        help="Optional number of sentences per chunk (e.g. 500). Disabled when 0.",
    )
    parser.add_argument(
        "--toc-scan-pages",
        type=int,
        default=30,
        help="Maximum number of initial PDF pages to scan for TOC chapter titles.",
    )
    parser.add_argument("--skip-pages", type=int, default=0, help="Skip N first pages (PDF only)")
    parser.add_argument(
        "--soft-delimiter",
        action="append",
        dest="soft_delimiters",
        default=None,
        help=(
            "Soft split delimiter for overlength sentences. "
            "Provide multiple times to set priority order. "
            f"Default: {DEFAULT_SOFT_DELIMITERS}"
        ),
    )
    parser.add_argument(
        "--remove-regex",
        action="append",
        dest="remove_patterns",
        default=None,
        help="Extra regex pattern to remove matching lines from PDF text before sentence splitting",
    )
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="Print the sentence list as JSON to stdout (ignored if --output is set)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    chapter_titles: list[str] = []

    if args.input_path.suffix.lower() == ".pdf":
        chapter_titles = extract_chapter_names_from_toc_pdf(
            path=args.input_path,
            max_scan_pages=args.toc_scan_pages,
        )
        print(
            f"Found {len(chapter_titles)} chapter titles in table of contents.",
            file=sys.stderr,
        )
        for idx, chapter in enumerate(chapter_titles, start=1):
            print(f"{idx}. \"{chapter}\"", file=sys.stderr)

    sentences = extract_sentences_from_path(
        input_path=args.input_path,
        min_length=args.min_length,
        max_length=args.max_length,
        soft_delimiters=args.soft_delimiters,
        skip_pages=args.skip_pages,
        chapter_titles_to_remove=chapter_titles,
        extra_remove_patterns=args.remove_patterns,
    )
    chunks = chunk_sentences(sentences, args.chunk_size) if args.chunk_size > 0 else [sentences]

    if args.output is not None:
        folder_path = os.path.dirname(args.output)
        os.makedirs(folder_path, exist_ok=True)

        if args.chunk_size > 0:
            written_paths = write_chunked_sentences_output(chunks, args.output)
            print(
                f"Wrote {len(sentences)} sentences into {len(written_paths)} chunks "
                f"(max {args.chunk_size} each)."
            )
            print("Chunk files:")
            for path in written_paths:
                print(path)
        else:
            write_sentences_output(sentences, args.output)
            print(f"Wrote {len(sentences)} sentences to {args.output}")
        return 0

    if args.stdout_json:
        payload = chunks if args.chunk_size > 0 else sentences
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if args.chunk_size > 0:
            for idx, chunk in enumerate(chunks, start=1):
                print(f"# chunk {idx}")
                for sentence in chunk:
                    print(sentence)
        else:
            for sentence in sentences:
                print(sentence)

    if args.chunk_size > 0:
        print(f"Total sentences: {len(sentences)} across {len(chunks)} chunks")
    else:
        print(f"Total sentences: {len(sentences)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
