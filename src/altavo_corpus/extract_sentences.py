#!/usr/bin/env python3
"""Extract sentence segments from PDF or UTF-8 text with min/max word constraints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from altavo_corpus.sentence_extractor import DEFAULT_SOFT_DELIMITERS
from altavo_corpus.sentence_extractor import WORDS_PER_SECOND
from altavo_corpus.sentence_extractor import chunk_sentences_by_max_minutes
from altavo_corpus.sentence_extractor import extract_chapter_names_from_toc_pdf
from altavo_corpus.sentence_extractor import extract_sentences_from_path
from altavo_corpus.sentence_extractor import write_chunk_sentence_length_histograms
from altavo_corpus.sentence_extractor import write_chunked_sentences_output


DESCRIPTION = (
    "Extract text from a PDF or TXT file and split into sentence segments "
    "with target word lengths in [min_length, max_length]."
)


def add_arguments(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("input_path", type=Path, help="Path to .pdf or .txt input")
    parser.add_argument("--output", type=Path, default=None, help="Optional output file (.txt or .json)")
    parser.add_argument("--min-length", type=int, default=5, help="Minimum words per sentence segment")
    parser.add_argument("--max-length", type=int, default=25, help="Maximum words per sentence segment")
    parser.add_argument(
        "--max-chunk-minutes",
        type=float,
        default=0.0,
        help=(
            "Optional maximum cumulative chunk duration in minutes. "
            f"Duration is estimated with {WORDS_PER_SECOND} words/second. Disabled when 0."
        ),
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
    parser.add_argument(
        "--plot-charts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Plot sentence-length histograms per chunk into <output_dir>/charts/ "
            "(enabled by default; use --no-plot-charts to disable)."
        ),
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    return add_arguments(argparse.ArgumentParser(description=DESCRIPTION))


def run(args: argparse.Namespace) -> int:
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
    chunks = (
        chunk_sentences_by_max_minutes(sentences, args.max_chunk_minutes)
        if args.max_chunk_minutes > 0
        else [sentences]
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)

        # Always write into a chunks/ folder (one file when --max-chunk-minutes=0)
        # so validate-corpus / convert-to-altavo-csv can point at one directory.
        written_paths = write_chunked_sentences_output(chunks, args.output)
        chunks_dir = written_paths[0].parent if written_paths else args.output.parent / "chunks"

        if args.max_chunk_minutes > 0:
            print(
                f"Wrote {len(sentences)} sentences into {len(written_paths)} chunks "
                f"(max {args.max_chunk_minutes:g} minutes each, estimated)."
            )
        else:
            print(f"Wrote {len(sentences)} sentences to {len(written_paths)} file(s) in {chunks_dir}")
        print("Chunk files:")
        for path in written_paths:
            print(path)

        if args.plot_charts:
            chart_paths = write_chunk_sentence_length_histograms(chunks, chunks_dir / args.output.name)
            print(f"Wrote {len(chart_paths)} chart(s) to {chunks_dir / 'charts'}")
        return 0

    if args.stdout_json:
        payload = chunks if args.max_chunk_minutes > 0 else sentences
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if args.max_chunk_minutes > 0:
            for idx, chunk in enumerate(chunks, start=1):
                print(f"# chunk {idx}")
                for sentence in chunk:
                    print(sentence)
        else:
            for sentence in sentences:
                print(sentence)

    if args.max_chunk_minutes > 0:
        print(f"Total sentences: {len(sentences)} across {len(chunks)} chunks")
    else:
        print(f"Total sentences: {len(sentences)}")
    return 0


def main() -> int:
    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
