"""Content keyword extraction — from each chapter's raw *content* (not its
LLM-generated summary; see pipelines/summary.py's module docstring for why
that switch was made), distinct from books.tags (user-/MyBooks-assigned
labels). Two extraction paths depending on the text's language, chosen
because a single Chinese-tuned tool doesn't carry over cleanly to English
text (see .claude/memory or the design discussion this was built from):

- Chinese (the "zh" bucket — also covers Traditional Chinese and Japanese,
  which are summarized in Chinese too, see pipelines/summary.py's
  _lang_bucket): jieba.analyse TF-IDF, restricted to noun-like POS tags plus
  'eng' (English proper nouns/terms that appear untranslated in an
  otherwise-Chinese text, e.g. book/character/product names) so they
  aren't silently dropped by the POS whitelist.
- English: jieba's Chinese-tuned IDF/POS tagging doesn't discriminate
  between English words (everything gets tagged 'eng', uniform default IDF),
  so this path uses NLTK's POS tagger instead, keeps only nouns/proper nouns
  (NN/NNS/NNP/NNPS — the standard "keywords are nouns" heuristic), and
  scores by simple term frequency (no IDF corpus available for this text).

Both return `[(term, weight), ...]` sorted by weight descending. Callers do
their own reduction across segments/chapters — see merge_topk below and
pipelines/summary.py's rolling aggregation, which keeps the intermediate
term set from growing unbounded across a long book instead of holding every
candidate from every chapter in memory until the very end.
"""

import logging
import re

logger = logging.getLogger(__name__)

_MIN_TERM_LEN = 2
_DEFAULT_TOP_K = 20

# jieba POS tags kept for Chinese extraction: nouns (n), place names (ns),
# other proper nouns (nz), organizations/institutions (nt), person names
# (nr), verb-derived nouns (vn), plus 'eng' for untranslated English terms
# (see module docstring) — deliberately excludes plain verbs/adjectives/
# function words, which carry little of a book's actual subject matter.
_ZH_ALLOW_POS = ("n", "ns", "nz", "nt", "nr", "vn", "eng")

# NLTK POS tags kept for English extraction: singular/plural common nouns
# and proper nouns.
_EN_NOUN_TAGS = {"NN", "NNS", "NNP", "NNPS"}
_EN_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z'-]*")

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


def _extract_zh(text: str, top_k: int) -> list[tuple[str, float]]:
    import jieba.analyse

    tags = jieba.analyse.extract_tags(text, topK=top_k, withWeight=True, allowPOS=_ZH_ALLOW_POS)
    return [(term, weight) for term, weight in tags if len(term.strip()) >= _MIN_TERM_LEN]


def _extract_en(text: str, top_k: int) -> list[tuple[str, float]]:
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

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:top_k]
    return [(term, float(count)) for term, count in ranked]


def extract_keywords(text: str, lang: str, top_k: int = _DEFAULT_TOP_K) -> list[tuple[str, float]]:
    """lang: "en" or "zh" (see pipelines/summary.py's _lang_bucket) — picks
    the extraction path. top_k bounds how many candidates come out of this
    one call — callers processing a book in segments/chapters pass a
    generously sized top_k here (bigger than the final desired count) and
    do their own cross-chunk reduction (see merge_topk), rather than relying
    on this function to see the whole book's text at once.

    Never raises: extraction failure (e.g. NLTK data missing) degrades to
    no keywords for this chunk of text rather than failing the whole
    summarization run."""
    if not text or not text.strip():
        return []
    try:
        return _extract_en(text, top_k) if lang == "en" else _extract_zh(text, top_k)
    except Exception:  # noqa: BLE001
        logger.exception("keyword extraction failed (lang=%s)", lang)
        return []


def merge_topk(totals: dict[str, float], candidates: list[tuple[str, float]], cap: int) -> dict[str, float]:
    """Adds candidates' weights into totals (summing on term collision), then
    prunes back down to the top `cap` terms by weight if it grew past that.
    Used at both levels of pipelines/summary.py's rolling reduction —
    segment-into-chapter and chapter-into-book — so the running dict stays
    bounded (a handful of merges' worth of terms, not one entry per
    candidate ever seen) no matter how many chapters/segments a book has.

    A term with low weight this call and cut here isn't gone for good if it
    matters — it just didn't make the cut yet; each call's top_k should be
    generous enough (see pipelines/summary.py's _KEYWORDS_PER_SEGMENT_TOP_K)
    that a term genuinely common across the book keeps re-qualifying and
    accumulating weight call over call."""
    for term, weight in candidates:
        totals[term] = totals.get(term, 0.0) + weight
    if len(totals) > cap:
        totals = dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:cap])
    return totals
