import logging
import re

logger = logging.getLogger(__name__)

# 章节摘要预算按字符换算时使用（中文约 1 字 ≈ 1 token）
CHARS_PER_TOKEN = 1.0

_ENCODING_NAMES = ("o200k_base", "cl100k_base")
_CJK = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af"
_FALLBACK_TOKEN_RE = re.compile(rf"[{_CJK}]|[A-Za-z0-9_]+|[^\sA-Za-z0-9_]")

_encoder = None
_encoder_initialized = False


def _get_encoder():
    global _encoder, _encoder_initialized
    if _encoder_initialized:
        return _encoder
    _encoder_initialized = True
    try:
        import tiktoken
    except ImportError:
        logger.warning("tiktoken 未安装，token 计数退化为近似值")
        return None
    for name in _ENCODING_NAMES:
        try:
            _encoder = tiktoken.get_encoding(name)
            logger.info("token 计数使用 tiktoken 编码 %s", name)
            return _encoder
        except Exception as exc:  # noqa: BLE001 - try the next encoding
            logger.warning("tiktoken 编码 %s 不可用: %s", name, exc)
    logger.warning("tiktoken 编码全部不可用，token 计数退化为近似值")
    return None


def count_tokens(text: str) -> int:
    if not text:
        return 0
    encoder = _get_encoder()
    if encoder is not None:
        try:
            return len(encoder.encode(text, disallowed_special=()))
        except Exception as exc:  # noqa: BLE001 - fall back to approximation
            logger.warning("tiktoken 计数失败，退化为近似值: %s", exc)
    return len(_FALLBACK_TOKEN_RE.findall(text))
