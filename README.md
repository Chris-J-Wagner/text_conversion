# Installation
run
```
uv tool install .
```

# Usage
A single `altavo-corpus` command with three subcommands, meant to be run in order:

```
altavo-corpus extract  book.pdf --output out/book.txt --max-chunk-minutes 2
altavo-corpus validate out/chunks --min-length 5 --max-length 25
altavo-corpus convert  out/chunks out/book.csv --language en-us
```

## extract
Reads a text file or PDF and splits it into sentences of a target length (`--min-length`,
`--max-length`), mainly by word count and delimiters. Output is one sentence per line, written
into a `chunks/` folder next to `--output` as `<num>_<name>.<ext>` (a single file unless
`--max-chunk-minutes` splits it into time-boxed chunks). By default it also plots the achieved
sentence-length distribution per chunk into `chunks/charts/` (disable with `--no-plot-charts`).

## validate
Points at a directory of corpus files (globs `*.txt`), reports how many sentences fall outside
`--min-length`/`--max-length` per file and overall, and re-plots the length histograms.
Use case is mainly for manual editing of the corpus after `extract` to ensure that the final corpus is clean and within the desired length bounds.

## convert
Converts one text file or a directory of corpus files into Altavo CSV rows `id|sentence|phonemes`.
Phonemes are produced with `phonemizer` (`--language`, `--backend`), which needs an `espeak`/`espeak-ng`
backend installed.
