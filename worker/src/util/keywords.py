"""Content keyword extraction from generated summary text (see
pipelines/summary.py) — distinct from books.tags (user-/MyBooks-assigned
labels). Two extraction paths depending on the summary's language, chosen
because a single Chinese-tuned tool doesn't carry over cleanly to English
text (see .claude/memory or the design discussion this was built from):

- Chinese (the "zh" bucket — also covers Traditional Chinese and Japanese,
  which are summarized in Chinese too, see pipelines/summary.py's
  _lang_bucket): jieba.analyse TF-IDF, restricted to noun-like POS tags plus
  'eng' (English proper nouns/terms that survive untranslated inside an
  otherwise-Chinese summary, e.g. book/character/product names) so they
  aren't silently dropped by the POS whitelist.
- English: jieba's Chinese-tuned IDF/POS tagging doesn't discriminate
  between English words (everything gets tagged 'eng', uniform default IDF),
  so this path uses NLTK's POS tagger instead, keeps only nouns/proper nouns
  (NN/NNS/NNP/NNPS — the standard "keywords are nouns" heuristic), and
  scores by simple term frequency (no IDF corpus available for this text).

Both return `[(term, weight), ...]` sorted by weight descending — the
caller (SummaryPipeline) sums weights across chapters for the whole-book
reduce step.
"""

import logging
import re

logger = logging.getLogger(__name__)

_MIN_TERM_LEN = 2

# jieba POS tags kept for Chinese extraction: nouns (n), place names (ns),
# other proper nouns (nz), organizations/institutions (nt), person names
# (nr), verb-derived nouns (vn), plus 'eng' for untranslated English terms
# (see module docstring) — deliberately excludes plain verbs/adjectives/
# function words, which carry little of a book's actual subject matter.
_ZH_ALLOW_POS = ("n", "ns", "nz", "nt", "nr", "vn", "eng")
_ZH_TOP_K = 20

# NLTK POS tags kept for English extraction: singular/plural common nouns
# and proper nouns.
_EN_NOUN_TAGS = {"NN", "NNS", "NNP", "NNPS"}
_EN_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]*")
_EN_TOP_K = 20

# Common function/auxiliary words NLTK's tagger can still let through as
# nouns often enough to be worth a hard block (e.g. "one", "thing") — a
# small supplement to POS filtering, not a replacement for it.
_EN_STOPWORDS = frozenset(
    """
    a an the this that these those is are was were be been being have has had
    do does did will would shall should can could may might must
    and or but if then than so because as of in on at to for with without
    from by about into over under again further once here there when where
    why how all any both each few more most other some such no nor not only
    own same so than too very s t just don now i you he she it we they
    what which who whom it its itself them their there thing things one way
    """.split()
)


def _extract_zh(text: str) -> list[tuple[str, float]]:
    import jieba.analyse

    tags = jieba.analyse.extract_tags(text, topK=_ZH_TOP_K, withWeight=True, allowPOS=_ZH_ALLOW_POS)
    return [(term, weight) for term, weight in tags if len(term.strip()) >= _MIN_TERM_LEN]


def _extract_en(text: str) -> list[tuple[str, float]]:
    import nltk

    tokens = nltk.word_tokenize(text)
    tagged = nltk.pos_tag(tokens)

    counts: dict[str, int] = {}
    for word, tag in tagged:
        if tag not in _EN_NOUN_TAGS:
            continue
        if not _EN_TOKEN_PATTERN.fullmatch(word):
            continue
        term = word.lower()
        if len(term) < _MIN_TERM_LEN or term in _EN_STOPWORDS:
            continue
        counts[term] = counts.get(term, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:_EN_TOP_K]
    return [(term, float(count)) for term, count in ranked]


def extract_keywords(text: str, lang: str) -> list[tuple[str, float]]:
    """lang: "en" or "zh" (see pipelines/summary.py's _lang_bucket) — picks
    the extraction path. Never raises: extraction failure (e.g. NLTK data
    missing) degrades to no keywords for this chunk of text rather than
    failing the whole summarization run."""
    if not text or not text.strip():
        return []
    try:
        return _extract_en(text) if lang == "en" else _extract_zh(text)
    except Exception:  # noqa: BLE001
        logger.exception("keyword extraction failed (lang=%s)", lang)
        return []
