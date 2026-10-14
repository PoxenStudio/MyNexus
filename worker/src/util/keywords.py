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

# Generic nouns that pass the POS filter above (they're legitimately tagged
# 'n'/'vn') but carry no book-specific meaning — academic/narrative
# meta-vocabulary ("受试者", "结果", "人们") that shows up across almost any
# book regardless of subject matter. jieba's default IDF corpus is a generic
# news corpus, so it doesn't reliably suppress these the way a corpus built
# from this book's own domain would; this is a hand-curated supplement to
# POS filtering, mirroring _EN_STOPWORDS below. Deliberately conservative —
# only words generic enough to be near-useless as a book-specific keyword in
# *any* book, not domain terms that happen to be common in one genre (e.g.
# "患者" is left out: too likely to be a real keyword for a medical book).
_ZH_STOPWORDS = frozenset(
    """
    受试者 参与者 被试 人们 大家 我们 他们 她们 它们 自己
    方法 研究 结果 目的 方式 问题 情况 内容 部分 过程
    原因 条件 基础 水平 程度 能力 特点 特征 现象 状态 状况
    系统 结构 模式 类型 方向 途径 手段 措施 办法 策略 机制 体系
    领域 范围 对象 目标 任务 要求 标准 原则 规律 规则
    观点 看法 思想 理论 概念 定义 意思 意义 价值 作用 功能 性质 性能
    优点 缺点 特色 风格 形式 材料 资料 信息 数据
    结论 发现 成果 成效 效果 效应 影响 结局
    时候 时间 地方 东西 事情 事物 方面
    目录 序言 前言 后记 附录 引言 开篇
    """.split()
)

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


def _register_foreign_names(text: str) -> None:
    """Scan for `CJK·CJK` sequences (Chinese translation names like 西尔维娅·薇尔)
    and register each side as a jieba dict entry so they don't get split into
    fragments (e.g. 西尔 instead of 西尔维娅).

    Length ≤4 on either side → register the full run (likely a complete name
    fragment); longer → only register the 2 chars closest to · so we don't
    accidentally include following non-name CJK content.
    """
    import jieba

    CJK = re.compile(r"[\u4e00-\u9fff]")
    seen: set[str] = set()

    def _add(part: str) -> None:
        if 2 <= len(part) <= 6 and part not in seen:
            seen.add(part)
            jieba.add_word(part, freq=10000, tag="nr")

    i = 0
    while i < len(text):
        if text[i] in "·・":
            j = i - 1
            while j >= 0 and CJK.match(text[j]):
                j -= 1
            left_run = text[j + 1 : i]
            k = i + 1
            while k < len(text) and CJK.match(text[k]):
                k += 1
            right_run = text[i + 1 : k]
            _add(left_run if len(left_run) <= 4 else left_run[-2:])
            _add(right_run if len(right_run) <= 4 else right_run[:2])
            i = k
        else:
            i += 1


def _extract_zh(text: str, top_k: int) -> list[tuple[str, float]]:
    import jieba.analyse

    _register_foreign_names(text)

    tags = jieba.analyse.extract_tags(text, topK=top_k, withWeight=True, allowPOS=_ZH_ALLOW_POS)
    return [
        (term, weight)
        for term, weight in tags
        if len(term.strip()) >= _MIN_TERM_LEN and term not in _ZH_STOPWORDS
    ]


def _extract_en(text: str, top_k: int) -> list[tuple[str, float]]:
    import nltk

    counts: dict[str, int] = {}
    try:
        tagged = nltk.pos_tag(nltk.word_tokenize(text))
    except LookupError:
        logger.warning("NLTK English models unavailable; using frequency-based keyword extraction")
        tagged = ((word, "NN") for word in _EN_TOKEN_PATTERN.findall(text))

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


def merge_topk(
    totals: dict[str, float],
    candidates: list[tuple[str, float]],
    cap: int,
    doc_freq: dict[str, int] | None = None,
) -> dict[str, float]:
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
    accumulating weight call over call.

    doc_freq, when passed, counts how many merge_topk calls (i.e. how many
    source documents — chapters, in pipelines/summary.py's book-level
    reduce) each term showed up in at all, regardless of whether it survives
    this call's cap prune. Callers doing per-document rolling reduction
    (one merge_topk call per document) can pass the same dict across the
    whole reduction and hand it to filter_by_doc_frequency afterwards to
    catch terms that are common *everywhere* rather than genuinely salient
    to a handful of documents — something the weight-based cap alone can't
    tell apart from a term that's simply frequent within the book."""
    for term, weight in candidates:
        totals[term] = totals.get(term, 0.0) + weight
        if doc_freq is not None:
            doc_freq[term] = doc_freq.get(term, 0) + 1
    if len(totals) > cap:
        totals = dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:cap])
    return totals


# Defaults for filter_by_doc_frequency below.
_DEFAULT_MAX_DOC_RATIO = 0.6
_DEFAULT_MIN_DOCS_FOR_FILTERING = 4


def filter_by_doc_frequency(
    totals: dict[str, float],
    doc_freq: dict[str, int],
    num_docs: int,
    max_doc_ratio: float = _DEFAULT_MAX_DOC_RATIO,
    min_docs_for_filtering: int = _DEFAULT_MIN_DOCS_FOR_FILTERING,
) -> dict[str, float]:
    """Drops terms that showed up in too large a share of the source
    documents (chapters, at the book level) — a term appearing in most/all
    chapters is acting as generic vocabulary for *this book*, not a
    chapter-specific topic marker, even if no fixed stopword list (see
    _ZH_STOPWORDS) happens to name it. This is a per-book, self-calibrating
    complement to that static list: it catches terms that are only generic
    in the context of this particular book (e.g. a recurring character name
    in a novel, or a domain term repeated in every chapter of a textbook),
    which no hand-curated list could anticipate.

    Skipped entirely when num_docs < min_docs_for_filtering — a book with
    only a handful of chapters doesn't give the ratio enough samples to be
    meaningful, and would otherwise risk wiping out real keywords just
    because a short book mentions its own subject in every chapter."""
    if num_docs < min_docs_for_filtering:
        return totals
    threshold = max_doc_ratio * num_docs
    return {term: weight for term, weight in totals.items() if doc_freq.get(term, 0) <= threshold}
