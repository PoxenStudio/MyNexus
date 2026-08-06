"""Splits long plain text into meaning-respecting segments — used by
pipelines/summary.py so a chapter too big for one LLM call gets map-reduced
(summarize each segment, then merge those summaries) instead of truncated
and silently losing whatever came after the cutoff (see docs/Todos.md).

Not HTML-aware: operates on the plain text nodes/parsers/epub_parser.py
already produced (one line per source paragraph/block — see its
_extract_text), not on markup. "段落" here means one of those lines.
"""

import re

# Where to start looking for a paragraph break to cut on. Chosen, not
# derived: big enough that a chapter doesn't get sliced into lots of tiny
# segments (each one is its own LLM call), small enough that a segment stays
# comfortably inside a small local model's context window.
DEFAULT_TARGET_CHARS = 10000

# Cut here unconditionally if no paragraph break was found by this point —
# same value pipelines/summary.py used as its old hard truncation limit, now
# repurposed as "the point past which we stop holding out for a paragraph
# break and fall back to a sentence boundary instead."
DEFAULT_HARD_LIMIT_CHARS = 12000

# Characters that end a sentence in Chinese and English text. Checked as the
# character immediately before a candidate cut point.
_SENTENCE_END_CHARS = "。！？.!?"


def split_into_segments(
    text: str,
    target_chars: int = DEFAULT_TARGET_CHARS,
    hard_limit_chars: int = DEFAULT_HARD_LIMIT_CHARS,
) -> list[str]:
    """Splits text into segments no single one longer than hard_limit_chars
    (except when a segment truly cannot be — see _find_cut below), each
    ending at a meaningful boundary, preferred in this order:

    1. A paragraph break ("\\n") at or after target_chars but before
       hard_limit_chars — the common case for normal prose.
    2. Failing that, the nearest sentence-ending punctuation at or before
       hard_limit_chars, so a segment ends after a complete sentence instead
       of mid-word even when a paragraph runs long.
    3. Failing even that (a punctuation-free run longer than hard_limit_chars
       — pathological, but e.g. a raw list/table might do this), a hard cut
       at hard_limit_chars. This is the only case that can still split
       mid-sentence.

    A text no longer than hard_limit_chars is returned as a single segment
    untouched — this is the common case and costs one LLM call, same as
    before this existed.
    """
    if len(text) <= hard_limit_chars:
        return [text] if text else []

    segments = []
    remaining = text
    while len(remaining) > hard_limit_chars:
        cut = _find_cut(remaining, target_chars, hard_limit_chars)
        segment = remaining[:cut].strip()
        if segment:
            segments.append(segment)
        remaining = remaining[cut:]
    remaining = remaining.strip()
    if remaining:
        segments.append(remaining)
    return segments


def _find_cut(text: str, target_chars: int, hard_limit_chars: int) -> int:
    # 1) paragraph break: the first "\n" at or after target_chars, as long as
    # it's not past hard_limit_chars (a paragraph break way out past the
    # limit doesn't help — the segment would already be oversized).
    newline_at = text.find("\n", target_chars)
    if 0 <= newline_at < hard_limit_chars:
        return newline_at + 1  # include the newline so the next segment doesn't start with a blank line

    # 2) sentence boundary: scan backward from hard_limit_chars so the
    # segment is as close to the target size as possible while still ending
    # cleanly. Anywhere in (target_chars, hard_limit_chars] counts, not just
    # right at the limit.
    for i in range(hard_limit_chars, target_chars, -1):
        if text[i - 1] in _SENTENCE_END_CHARS:
            return i

    # 3) give up — neither boundary exists in range, hard-cut.
    return hard_limit_chars


if __name__ == "__main__":
    # Standalone test: run from worker/src with
    #   python3 -m util.text_split path/to/file.txt
    import argparse

    parser = argparse.ArgumentParser(description="Split a text file into segments and print their boundaries.")
    parser.add_argument("file_path")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET_CHARS)
    parser.add_argument("--hard-limit", type=int, default=DEFAULT_HARD_LIMIT_CHARS)
    args = parser.parse_args()

    with open(args.file_path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    segs = split_into_segments(raw, args.target, args.hard_limit)
    print(f"{len(raw)} chars -> {len(segs)} segment(s)")
    for i, seg in enumerate(segs):
        tail = re.sub(r"\s+", " ", seg[-40:])
        print(f"  [{i + 1}/{len(segs)}] {len(seg)} chars, ends: ...{tail!r}")
