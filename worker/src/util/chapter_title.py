import re

# Every parser runs extracted chapter titles through here so titles land
# consistently in the DB regardless of source format — e.g. EPUB TOC entries
# and OCR'd/plain-text headings sometimes carry stray/internal whitespace
# ("索 引", "Chapter  3") that a plain .strip() wouldn't catch.
_WHITESPACE_RE = re.compile(r"\s+")

# Chapters whose (cleaned) title is exactly one of these never carry content
# worth summarizing/embedding — an index or bibliography is just a list of
# page refs/citations, not prose — so parsers drop them outright rather than
# feeding them into chunking/summarization.
_SKIPPABLE_TITLES = {"索引", "参考书目", "index", "bibliography"}


def clean_chapter_title(title: str) -> str:
    """Strip *all* whitespace (not just leading/trailing) from a chapter title."""
    return _WHITESPACE_RE.sub("", title or "")


def is_skippable_chapter_title(cleaned_title: str) -> bool:
    """True if a (already-cleaned, via clean_chapter_title) title marks a
    chapter that should be dropped entirely, e.g. an index or bibliography."""
    return cleaned_title.casefold() in _SKIPPABLE_TITLES
