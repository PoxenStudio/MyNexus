import re

# Every parser runs extracted chapter titles through here so titles land
# consistently in the DB regardless of source format — e.g. EPUB TOC entries
# and OCR'd/plain-text headings sometimes carry stray/internal whitespace
# ("索 引", "Chapter  3") that a plain .strip() wouldn't catch.
_WHITESPACE_RE = re.compile(r"\s+")

# Chapters whose (cleaned) title is exactly one of these never carry content
# worth summarizing/embedding
_SKIPPABLE_TITLES = {
    "索引",
    "参考书目",
    "扉页",
    "书名页",
    "封面",
    "目录",
    "版权页",
    "版权信息",
    "出版信息",
    "index",
    "bibliography",
    "cover",
    "contents",
    "titlepage",
    "copyright",
    "copyrightpage",
}


def clean_chapter_title(title: str) -> str:
    """Strip *all* whitespace (not just leading/trailing) from a chapter title."""
    return _WHITESPACE_RE.sub("", title or "")


def is_skippable_chapter_title(cleaned_title: str) -> bool:
    """True if a (already-cleaned, via clean_chapter_title) title marks a
    chapter that should be dropped entirely, e.g. an index or bibliography."""
    return cleaned_title.casefold() in _SKIPPABLE_TITLES
