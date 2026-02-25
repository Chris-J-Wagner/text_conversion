#!/usr/bin/env python3
"""Validate chunked sentence corpora against min/max word constraints."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from src.sentence_extractor import count_words
from src.sentence_extractor import write_chunk_sentence_length_histograms


def _chunk_sort_key(path: Path) -> tuple[str, int, str]:
    match = re.search(r"_(?:chunk|chunks)_(\d+)\.txt$", path.name)
    if match:
        prefix = path.name[: match.start()]
        return prefix, int(match.group(1)), path.name
    return path.stem, 10**9, path.name


def _load_chunk_sentences(path: Path, encoding: str = "utf-8") -> list[str]:
    return [line.strip() for line in path.read_text(encoding=encoding).splitlines() if line.strip()]


def _find_violating_indices(
    sentences: list[str],
    min_length: int,
    max_length: int,
) -> list[int]:
    violations: list[int] = []
    for idx, sentence in enumerate(sentences, start=1):
        length = count_words(sentence)
        if length < min_length or length > max_length:
            violations.append(idx)
    return violations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate chunk files in a directory, replot per-chunk sentence-length histograms, "
            "and report min/max length violations per chunk."
        )
    )
    parser.add_argument("chunks_dir", type=Path, help="Directory containing chunk .txt files")
    parser.add_argument("--min-length", type=int, required=True, help="Minimum words per sentence")
    parser.add_argument("--max-length", type=int, required=True, help="Maximum words per sentence")
    parser.add_argument(
        "--pattern",
        action="append",
        default=None,
        help=(
            "Glob pattern for chunk files. Repeatable. "
            "Defaults: '*_chunk_*.txt' and '*_chunks_*.txt'"
        ),
    )
    parser.add_argument("--encoding", default="utf-8", help="Text file encoding (default: utf-8)")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.min_length < 1:
        raise ValueError("--min-length must be >= 1")
    if args.max_length < args.min_length:
        raise ValueError("--max-length must be >= --min-length")

    patterns = args.pattern or ["*_chunk_*.txt", "*_chunks_*.txt"]
    chunk_paths = {
        path.resolve()
        for pattern in patterns
        for path in args.chunks_dir.glob(pattern)
        if path.is_file()
    }

    if not chunk_paths:
        raise FileNotFoundError(
            f"No chunk files found in '{args.chunks_dir}' for patterns: {patterns}"
        )

    sorted_paths = sorted((Path(p) for p in chunk_paths), key=_chunk_sort_key)
    chunks = [_load_chunk_sentences(path, encoding=args.encoding) for path in sorted_paths]

    # Replot/overwrite charts in <chunks_dir>/charts/
    chart_anchor_path = args.chunks_dir / "__validation_anchor__.txt"
    chart_paths = write_chunk_sentence_length_histograms(chunks, chart_anchor_path)
    print(f"Replotted {len(chart_paths)} chart(s) in {args.chunks_dir / 'charts'}")

    total_sentences = 0
    total_violations = 0

    for path, sentences in zip(sorted_paths, chunks):
        violations = _find_violating_indices(
            sentences=sentences,
            min_length=args.min_length,
            max_length=args.max_length,
        )
        total = len(sentences)
        count = len(violations)
        pct = (100.0 * count / total) if total else 0.0

        total_sentences += total
        total_violations += count

        print(f"\n{path.name}")
        print(f"violations: {count}/{total} ({pct:.2f}%)")
        print(f"line_indices: {violations}")

    overall_pct = (100.0 * total_violations / total_sentences) if total_sentences else 0.0
    print("\nOverall")
    print(f"violations: {total_violations}/{total_sentences} ({overall_pct:.2f}%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
