#!/usr/bin/env python3
"""Convert sentence text files to Altavo-style CSV rows: id|sentence|phonemes."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


def _chunk_sort_key(path: Path) -> tuple[str, int, str]:
    match = re.search(r"_(?:chunk|chunks)_(\d+)\.txt$", path.name)
    if match:
        prefix = path.name[: match.start()]
        return prefix, int(match.group(1)), path.name
    return path.stem, 10**9, path.name


def _load_sentences(path: Path, encoding: str) -> list[str]:
    return [line.strip() for line in path.read_text(encoding=encoding).splitlines() if line.strip()]


def _collect_input_files(input_path: Path, patterns: list[str] | None) -> list[Path]:
    if input_path.is_file():
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    globs = patterns or ["*_chunk_*.txt", "*_chunks_*.txt"]
    files = {
        p.resolve()
        for pattern in globs
        for p in input_path.glob(pattern)
        if p.is_file()
    }
    if not files:
        raise FileNotFoundError(
            f"No text files found in '{input_path}' for patterns: {globs}"
        )

    return sorted((Path(p) for p in files), key=_chunk_sort_key)


def _phonemize_sentences(
    sentences: list[str],
    language: str,
    backend: str,
    batch_size: int,
) -> list[str]:
    try:
        from phonemizer import phonemize
    except ImportError as exc:
        raise RuntimeError(
            "phonemizer is required. Install it with: pip install phonemizer"
        ) from exc

    out: list[str] = []
    for start in range(0, len(sentences), batch_size):
        batch = sentences[start : start + batch_size]
        tx_batch = phonemize(
            batch,
            language=language,
            backend=backend,
            strip=True,
            preserve_punctuation=False,
            language_switch="remove-flags",
        )
        out.extend(tx_batch)
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert one sentence .txt file or a directory of chunk .txt files "
            "to Altavo-formatted CSV rows: id|sentence|phonemes"
        )
    )
    parser.add_argument("input_path", type=Path, help="Input .txt file or directory")
    parser.add_argument("output_csv", type=Path, help="Output CSV path")
    parser.add_argument("--language", default="en-us", help="Phonemizer language (default: en-us)")
    parser.add_argument("--backend", default="espeak", help="Phonemizer backend (default: espeak)")
    parser.add_argument("--batch-size", type=int, default=500, help="Phonemization batch size")
    parser.add_argument(
        "--pattern",
        action="append",
        default=None,
        help=(
            "Glob pattern for directory input (repeatable). "
            "Defaults: '*_chunk_*.txt' and '*_chunks_*.txt'"
        ),
    )
    parser.add_argument("--encoding", default="utf-8", help="Text file encoding (default: utf-8)")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.batch_size < 1:
        raise ValueError("--batch-size must be >= 1")

    files = _collect_input_files(args.input_path, args.pattern)

    sentences: list[str] = []
    for file in files:
        sentences.extend(_load_sentences(file, encoding=args.encoding))

    phonemes = _phonemize_sentences(
        sentences=sentences,
        language=args.language,
        backend=args.backend,
        batch_size=args.batch_size,
    )

    if len(phonemes) != len(sentences):
        raise RuntimeError("Phonemizer output length mismatch")

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", encoding="utf-8") as f:
        for idx, (sentence, tx) in enumerate(zip(sentences, phonemes)):
            if "<oov>" in tx:
                raise RuntimeError(f"OOV token in sentence index {idx}: {tx}")
            f.write(f"{idx}|{sentence}|{tx}\n")

    print(f"Wrote {len(sentences)} rows to {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
