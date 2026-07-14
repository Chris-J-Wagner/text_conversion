#!/usr/bin/env python3
"""Single `altavo-corpus` entry point dispatching to the corpus subcommands."""

from __future__ import annotations

import argparse

from altavo_corpus import convert_to_altavo_csv, extract_sentences, validate_corpus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="altavo-corpus",
        description="Convert documents into sentence corpora and Altavo CSVs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, module, help_text in (
        ("extract", extract_sentences, "Extract sentences from a PDF/TXT into a corpus"),
        ("validate", validate_corpus, "Validate corpus files and replot histograms"),
        ("convert", convert_to_altavo_csv, "Convert a corpus into Altavo CSV rows"),
    ):
        sub = subparsers.add_parser(name, help=help_text, description=module.DESCRIPTION)
        module.add_arguments(sub)
        sub.set_defaults(_run=module.run)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args._run(args)


if __name__ == "__main__":
    raise SystemExit(main())
