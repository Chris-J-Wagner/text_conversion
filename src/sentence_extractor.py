"""Utilities for extracting and length-balancing sentences from PDF or UTF-8 text."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Sequence

DEFAULT_SOFT_DELIMITERS: list[str] = [" – ", "…", ", "]
DEFAULT_CHAPTER_PATTERNS: list[str] = [
    # r"^\s*(chapter|kapitel|teil)\s+[\w\-\.\:\/ivxlcdm\d]+\s*$",
    r"^\s*(table of contents|contents?|inhaltsverzeichnis)\s*$",
    r"^\s*[IVXLCDM]+\s*$",
    r"^\s*\d+\s*$",
    r"^\s*\d+\s*[\/-]\s*\d+\s*$",
    r"(CHAPTER\s+[IVXLCDM]+\s*\.)(.+?)\d"
]
TOC_HEADER_PATTERN = re.compile(r"\b(table of contents|contents|inhaltsverzeichnis)\b", flags=re.IGNORECASE)


def count_words(text: str) -> int:
    """Return the number of words in a string."""
    return sum(1 for token in text.split() if any(ch.isalnum() for ch in token))


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _looks_like_heading(line: str) -> bool:
    """Heuristic for short standalone chapter-like headings."""
    cleaned = _normalize_whitespace(line)
    if not cleaned:
        return False

    if re.search(r"[.!?…,:;]", cleaned):
        return False

    words = cleaned.split()
    if len(words) > 8:
        return False

    if not re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", cleaned):
        return False

    return cleaned.isupper() or cleaned.istitle()


def _normalize_title_key(text: str) -> str:
    """Normalize a title/heading for robust equality checks."""
    normalized = _normalize_whitespace(text).lower()
    normalized = re.sub(r"^(chapter|kapitel|teil)\s+", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(
        r"^(?:[ivxlcdm]+|\d+)(?:[\.\):\-]\s*|\s+)",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"\s+\d+$", "", normalized)
    normalized = re.sub(r"[^\wÀ-ÖØ-öø-ÿ]+", " ", normalized)
    return _normalize_whitespace(normalized)


def _parse_toc_line(line: str, in_toc_region: bool) -> str | None:
    """Parse a TOC line into a chapter title if possible."""
    cleaned = _normalize_whitespace(line)
    if not cleaned or len(cleaned) > 180:
        return None

    if TOC_HEADER_PATTERN.search(cleaned):
        return None

    title_patterns = [
        # "I. Down the Rabbit-Hole .... 1", "Chapter 1: Something 12"
        r"^(?:chapter|kapitel|teil)?\s*(?:[IVXLCDM]+|\d+)(?:[\.\):\-]\s*|\s+)(?P<title>.+?)\s*(?:\.{2,}\s*\d+|\s+\d+)\s*$",
        # "Down the Rabbit-Hole .... 1"
        r"^(?P<title>.+?)\s*\.{2,}\s*\d+\s*$",
        # "Chapter 1 Down the Rabbit-Hole"
        r"^(?:chapter|kapitel|teil)\s*(?:[IVXLCDM]+|\d+)?[\.\):\-]?\s*(?P<title>.+?)\s*$",
    ]

    for pattern in title_patterns:
        match = re.match(pattern, cleaned, flags=re.IGNORECASE)
        if not match:
            continue
        title = _normalize_whitespace(match.group("title").strip(" -–—:;,."))
        if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", title) and 1 <= len(title.split()) <= 16:
            return title

    # Fallback for TOC regions where extraction dropped page numbers/leaders:
    # "I Down the Rabbit-Hole"
    if in_toc_region:
        match = re.match(
            r"^(?:[IVXLCDM]+|\d+)(?:[\.\):\-]\s*|\s+)(?P<title>.+?)\s*$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if match:
            title = _normalize_whitespace(match.group("title").strip(" -–—:;,."))
            if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", title) and 1 <= len(title.split()) <= 16:
                return title

    return None


def _find_repeated_header_footer_lines(
    pages_lines: list[list[str]],
    lookaround_lines: int = 2,
    repeat_ratio: float = 0.6,
) -> set[str]:
    """Find lines that repeat across many page headers/footers."""
    if not pages_lines:
        return set()

    page_count = len(pages_lines)
    candidates: list[str] = []
    for lines in pages_lines:
        if not lines:
            continue
        candidates.extend(lines[:lookaround_lines])
        candidates.extend(lines[-lookaround_lines:])

    counts = Counter(candidates)
    repeated = {
        line
        for line, freq in counts.items()
        if freq >= 2 and (freq / page_count) >= repeat_ratio
    }
    return repeated


def _chapter_title_match_span(
    lines: Sequence[str],
    start_idx: int,
    chapter_title_keys: set[str],
    max_span_lines: int = 4,
) -> int:
    """Return number of lines to skip if consecutive lines match a chapter title."""
    combined = ""
    for offset in range(max_span_lines):
        idx = start_idx + offset
        if idx >= len(lines):
            break

        piece = _normalize_whitespace(lines[idx])
        if not piece:
            break

        combined = _normalize_whitespace(f"{combined} {piece}") if combined else piece
        if _normalize_title_key(combined) in chapter_title_keys:
            return offset + 1

    return 0


def extract_chapter_names_from_toc_pdf(path: str | Path, max_scan_pages: int = 30) -> list[str]:
    """Extract chapter titles from a PDF table of contents."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF input. Install via: pip install pypdf") from exc

    reader = PdfReader(str(path))
    scan_pages = min(max_scan_pages, len(reader.pages))

    chapter_titles: list[str] = []
    seen_keys: set[str] = set()
    in_toc_region = False
    non_toc_page_streak = 0

    for page_idx in range(scan_pages):
        page_text = reader.pages[page_idx].extract_text() or ""
        lines = [_normalize_whitespace(line) for line in page_text.splitlines()]
        lines = [line for line in lines if line]

        if not lines:
            if in_toc_region:
                non_toc_page_streak += 1
            continue

        has_toc_header = any(TOC_HEADER_PATTERN.search(line) for line in lines)
        page_titles: list[str] = []
        for line in lines:
            title = _parse_toc_line(line, in_toc_region=in_toc_region or has_toc_header)
            if title:
                page_titles.append(title)

        if has_toc_header or len(page_titles) >= 3:
            in_toc_region = True

        if not in_toc_region:
            continue

        if page_titles:
            non_toc_page_streak = 0
            for title in page_titles:
                key = _normalize_title_key(title)
                if key and key not in seen_keys:
                    seen_keys.add(key)
                    chapter_titles.append(title)
        else:
            non_toc_page_streak += 1
            if non_toc_page_streak >= 2:
                break

    return chapter_titles


def extract_text_from_pdf(
    path: str | Path,
    skip_pages: int = 0,
    remove_repeated_headers_footers: bool = True,
    drop_probable_headings: bool = True,
    chapter_patterns: Sequence[str] | None = None,
    chapter_titles_to_remove: Sequence[str] | None = None,
    extra_remove_patterns: Sequence[str] | None = None,
) -> str:
    """Extract and clean text from a PDF file."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("pypdf is required for PDF input. Install via: pip install pypdf") from exc

    reader = PdfReader(str(path))
    raw_pages: list[str] = []

    for page in reader.pages[skip_pages:]:
        page_text = page.extract_text() or ""
        raw_pages.append(page_text)

    pages_lines: list[list[str]] = []
    for page_text in raw_pages:
        lines = [_normalize_whitespace(line) for line in page_text.splitlines()]
        lines = [line for line in lines if line]
        pages_lines.append(lines)

    repeated_lines: set[str] = set()
    if remove_repeated_headers_footers:
        repeated_lines = _find_repeated_header_footer_lines(pages_lines)

    compiled_patterns: list[re.Pattern[str]] = []
    pattern_list = list(DEFAULT_CHAPTER_PATTERNS if chapter_patterns is None else chapter_patterns)
    pattern_list.extend(extra_remove_patterns or [])
    
    for pattern in pattern_list:
        compiled_patterns.append(re.compile(pattern, flags=re.IGNORECASE))
    chapter_title_keys = {
        key for key in (_normalize_title_key(title) for title in (chapter_titles_to_remove or [])) if key
    }

    pages_text: list[str] = []
    for lines in pages_lines:
        kept: list[str] = []
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            if line in repeated_lines:
                idx += 1
                continue

            if any(pattern.search(line) for pattern in compiled_patterns):
                idx += 1
                continue

            if chapter_title_keys:
                span = _chapter_title_match_span(lines, idx, chapter_title_keys)
                if span > 0:
                    idx += span
                    continue

            if drop_probable_headings and _looks_like_heading(line):
                idx += 1
                continue

            kept.append(line)
            idx += 1

        if not kept:
            continue

        # Repair line-break hyphenation from PDF extraction.
        rebuilt: list[str] = []
        for line in kept:
            if rebuilt and rebuilt[-1].endswith("-") and line:
                rebuilt[-1] = rebuilt[-1][:-1] + line
            else:
                rebuilt.append(line)

        page_text = " ".join(rebuilt)
        page_text = _normalize_whitespace(page_text)
        if page_text:
            pages_text.append(page_text)

    return _normalize_whitespace(" ".join(pages_text))


def extract_text_from_txt(path: str | Path) -> str:
    """Read UTF-8 plain text."""
    return _normalize_whitespace(Path(path).read_text(encoding="utf-8"))


def _split_on_periods(text: str) -> list[str]:
    """Split text into sentence-like units on periods while retaining periods."""
    if not text:
        return []
    pattern = re.compile(r'.+?(?:\.(?:["”’)\]]*)(?=\s|$|[A-ZÀ-ÖØ-Þ])|$)')
    return [m.group(0).strip() for m in pattern.finditer(text) if m.group(0).strip()]


def _split_once_balanced(sentence: str, delimiter: str, min_length: int) -> tuple[str, str] | None:
    """Split once on a delimiter at the most balanced split point."""
    if delimiter not in sentence:
        return None

    candidates: list[tuple[float, str, str]] = []
    for match in re.finditer(re.escape(delimiter), sentence):
        split_idx = match.end()
        left = sentence[:split_idx].strip()
        right = sentence[split_idx:].strip()

        if not left or not right:
            continue

        left_words = count_words(left)
        right_words = count_words(right)

        min_penalty = 0.0
        if left_words < min_length:
            min_penalty += float(min_length - left_words) * 2.0
        if right_words < min_length:
            min_penalty += float(min_length - right_words) * 2.0

        balance_penalty = abs(left_words - right_words)
        score = min_penalty + float(balance_penalty)
        candidates.append((score, left, right))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    _, best_left, best_right = candidates[0]
    return best_left, best_right


def _split_long_sentence(
    sentence: str,
    max_length: int,
    min_length: int,
    soft_delimiters: Sequence[str],
) -> list[str]:
    """Split an overlength sentence using hierarchical delimiter priority."""
    segments = [sentence]

    for delimiter in soft_delimiters:
        changed = True
        while changed:
            changed = False
            next_segments: list[str] = []

            for seg in segments:
                if count_words(seg) <= max_length:
                    next_segments.append(seg)
                    continue

                split_pair = _split_once_balanced(seg, delimiter, min_length=min_length)
                if split_pair is None:
                    next_segments.append(seg)
                    continue

                left, right = split_pair
                next_segments.extend([left, right])
                changed = True

            segments = next_segments

    return segments


def _ends_with_soft_delimiter(segment: str, soft_delimiters: Sequence[str]) -> bool:
    """Check if a segment ends with a configured soft delimiter token."""
    tail = segment.rstrip()
    for delimiter in soft_delimiters:
        token = delimiter.strip()
        if token and tail.endswith(token):
            return True
    return False


def _merge_soft_splits_when_within_max(
    segments: Sequence[str],
    max_length: int,
    soft_delimiters: Sequence[str],
) -> list[str]:
    """Re-merge soft-delimiter splits when combined length stays within max."""
    if not segments:
        return []

    merged: list[str] = []
    idx = 0
    while idx < len(segments):
        current = segments[idx].strip()
        while (
            idx + 1 < len(segments)
            and _ends_with_soft_delimiter(current, soft_delimiters)
        ):
            candidate = _normalize_whitespace(f"{current} {segments[idx + 1]}")
            if count_words(candidate) > max_length:
                break
            current = candidate
            idx += 1
        merged.append(current)
        idx += 1

    return merged


def _merge_short_segments(
    segments: Sequence[str],
    min_length: int,
    max_length: int,
) -> list[str]:
    """Merge neighboring short segments and prefer staying below max_length."""
    if not segments:
        return []

    merged: list[str] = []
    idx = 0

    while idx < len(segments):
        current = segments[idx].strip()
        if not current:
            idx += 1
            continue

        while count_words(current) < min_length and idx + 1 < len(segments):
            nxt = segments[idx + 1].strip()
            if not nxt:
                idx += 1
                continue

            candidate = _normalize_whitespace(f"{current} {nxt}")
            candidate_len = count_words(candidate)

            # Prioritize reaching min length, but avoid exceeding max when feasible.
            if candidate_len <= max_length or count_words(current) < min_length:
                current = candidate
                idx += 1
            else:
                break

        if count_words(current) < min_length and merged:
            back_candidate = _normalize_whitespace(f"{merged[-1]} {current}")
            back_candidate_len = count_words(back_candidate)
            if back_candidate_len <= max_length or count_words(merged[-1]) < min_length:
                merged[-1] = back_candidate
            else:
                merged.append(current)
        else:
            merged.append(current)

        idx += 1

    return merged


def split_text_into_sentences(
    text: str,
    min_length: int,
    max_length: int,
    soft_delimiters: Sequence[str] | None = None,
) -> list[str]:
    """Split text into sentences and balance lengths toward [min_length, max_length]."""
    if min_length < 1:
        raise ValueError("min_length must be >= 1")
    if max_length < min_length:
        raise ValueError("max_length must be >= min_length")

    delimiters = list(DEFAULT_SOFT_DELIMITERS if soft_delimiters is None else soft_delimiters)

    text = _normalize_whitespace(text)
    if not text:
        return []

    base_sentences = _split_on_periods(text)

    split_sentences: list[str] = []
    for sentence in base_sentences:
        if count_words(sentence) <= max_length:
            split_sentences.append(sentence)
            continue

        split_sentences.extend(
            _split_long_sentence(
                sentence=sentence,
                max_length=max_length,
                min_length=min_length,
                soft_delimiters=delimiters,
            )
        )

    split_sentences = _merge_soft_splits_when_within_max(
        split_sentences,
        max_length=max_length,
        soft_delimiters=delimiters,
    )
    merged = _merge_short_segments(split_sentences, min_length=min_length, max_length=max_length)
    return [_normalize_whitespace(sentence) for sentence in merged if sentence.strip()]


def extract_sentences_from_path(
    input_path: str | Path,
    min_length: int,
    max_length: int,
    soft_delimiters: Sequence[str] | None = None,
    skip_pages: int = 0,
    chapter_titles_to_remove: Sequence[str] | None = None,
    extra_remove_patterns: Sequence[str] | None = None,
) -> list[str]:
    """Extract text from TXT/PDF and split into balanced sentence segments."""
    path = Path(input_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        text = extract_text_from_pdf(
            path=path,
            skip_pages=skip_pages,
            chapter_titles_to_remove=chapter_titles_to_remove,
            extra_remove_patterns=extra_remove_patterns,
        )
    elif suffix == ".txt":
        text = extract_text_from_txt(path)
    else:
        raise ValueError(f"Unsupported input extension: {suffix}. Use .pdf or .txt")

    return split_text_into_sentences(
        text=text,
        min_length=min_length,
        max_length=max_length,
        soft_delimiters=soft_delimiters,
    )


def write_sentences_output(sentences: Sequence[str], output_path: str | Path) -> None:
    """Write output as newline text (.txt) or JSON list (.json)."""
    path = Path(output_path)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(list(sentences), ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        path.write_text("\n".join(sentences) + "\n", encoding="utf-8")


def chunk_sentences(sentences: Sequence[str], chunk_size: int) -> list[list[str]]:
    """Split a sentence list into fixed-size chunks."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be >= 1")

    chunks: list[list[str]] = []
    for idx in range(0, len(sentences), chunk_size):
        chunks.append(list(sentences[idx : idx + chunk_size]))
    return chunks


def write_chunked_sentences_output(
    sentence_chunks: Sequence[Sequence[str]],
    output_path: str | Path,
) -> list[Path]:
    """Write sentence chunks to numbered files derived from output_path."""
    path = Path(output_path)
    suffix = path.suffix if path.suffix else ".txt"
    base = path.with_suffix("")

    written_paths: list[Path] = []
    for idx, chunk in enumerate(sentence_chunks, start=1):
        chunk_path = base.parent / f"{base.name}_chunk_{idx:04d}{suffix}"
        write_sentences_output(chunk, chunk_path)
        written_paths.append(chunk_path)

    return written_paths
