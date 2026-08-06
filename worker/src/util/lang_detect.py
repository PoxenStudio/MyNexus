"""Title-based language detection — ported from MyBooks'
webserver/utils.py:detect_title_language(), same detection rules (see that
docstring for the priority reasoning: Traditional Chinese > Simplified
Chinese > Japanese > same-in-both-scripts fallback).

Used by pipelines/ingestion.py instead of the embedded-file-metadata
language field: for directly uploaded books that field is unreliable
(missing on TXT entirely, often wrong/default on EPUB), while the title is
almost always present and language-bearing.

Only distinguishes CJK scripts — an ASCII-only title returns None, which
callers (ingestion.py) treat as "not Chinese/Japanese", i.e. English, per
the project's simplified two-way language split (see
pipelines/summary.py's _lang_bucket).

Return codes match MyBooks' languageCodes scheme (app/src/utils/languageCodes.js
— 3-letter codes, "zha" is MyBooks' own non-ISO code for Traditional Chinese,
not a typo) rather than BCP-47, so books.language stays wire-compatible with
values a future MyBooks integration would send via UpdateBookRequest.Language,
and with the web-ui's language picker (see components/LanguagePicker or
BookDetailView's language editor) which lists the same code set.
"""

import logging
import re

logger = logging.getLogger(__name__)

# 日文假名 Unicode 区间：平假名 U+3040-309F，片假名 U+30A0-30FF
_KANA_PATTERN = re.compile(r"[぀-ヿ]")

# CJK 汉字区间：基本区 U+4E00-9FFF，扩展 A 区 U+3400-4DBF
_HAN_PATTERN = re.compile(r"[一-鿿㐀-䶿]")

TRADITIONAL_CHINESE_CODE = "zha"
SIMPLIFIED_CHINESE_CODE = "zho"
JAPANESE_CODE = "jpn"

# 常见繁体中文专有字符（在 Simplified 中对应不同字形），用于 opencc 不可用时的 fallback 检测。
_TRADITIONAL_ONLY_CHARS = frozenset(
    "書電來說話這個時會對學問國務現實際應當來們點進開關處還"
    "歡樂體動設計資訊傳說標準環境網絡變換預算發展運動認識"
    "義務條件結構機制選擇統計監督繼續識別溝通維護數據處理"
    "歷史文化藝術哲學經濟組織機構協議協作協調決策執行方針"
    "與並從內外長短廣狹強弱快慢遠近輕重高低深淺寬窄早晚"
    "後前左右東西南北上下中外新舊多少大小"
)


def _fallback_has_traditional(text: str) -> bool:
    return any(c in _TRADITIONAL_ONLY_CHARS for c in text)


def _is_traditional_chinese(text: str) -> bool:
    if not text or all(ord(c) < 128 for c in text):
        return False
    try:
        import opencc

        converted = opencc.OpenCC("t2s").convert(text)
        return converted != text
    except Exception as exc:  # noqa: BLE001
        logger.debug("opencc unavailable (%s), using fallback traditional-char check", exc)
        return _fallback_has_traditional(text)


def detect_title_language(text: str) -> str | None:
    """检测书名文本对应的语言代码。判定顺序：繁体中文 > 简体中文 > 日文 >
    简繁同形兜底（含汉字且不含假名时按简体中文处理）。

    :param text: 书名文本。
    :return: TRADITIONAL_CHINESE_CODE / SIMPLIFIED_CHINESE_CODE / JAPANESE_CODE，
             无法判定（含纯 ASCII 标题）时返回 None。
    """
    if not text:
        return None
    if all(ord(c) < 128 for c in text):
        return None

    if _is_traditional_chinese(text):
        return TRADITIONAL_CHINESE_CODE

    try:
        import opencc

        if opencc.OpenCC("s2t").convert(text) != text:
            return SIMPLIFIED_CHINESE_CODE
    except Exception as exc:  # noqa: BLE001
        logger.debug("opencc unavailable (%s), skip simplified check", exc)

    if _KANA_PATTERN.search(text):
        return JAPANESE_CODE

    if _HAN_PATTERN.search(text):
        return SIMPLIFIED_CHINESE_CODE

    return None
