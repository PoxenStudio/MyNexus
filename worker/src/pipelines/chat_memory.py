import logging
from typing import Callable

logger = logging.getLogger(__name__)

MIN_COMPRESSIBLE_MESSAGES = 4
MAX_SOURCE_CHARS = 12000
MAX_SUMMARY_CHARS = 2400
COMPRESS_TEMPERATURE = 0.2
COMPRESS_MAX_TOKENS = 700

_SYSTEM_PROMPT = (
    "You compress chat history for a book knowledge-base assistant. "
    "Produce durable memory only:\n"
    "- user preferences, decisions\n"
    "- book-specific facts already established\n"
    "- unresolved tasks / pending questions\n"
    "- useful context for future replies\n"
    "Do NOT include filler conversation. Keep it concise, neutral, "
    "and in the user's language when clear."
)


def _format_older(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        role = "User" if m.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {m.get('content', '')}")
    text = "\n".join(lines)
    if len(text) > MAX_SOURCE_CHARS:
        logger.warning(
            "memory compression source truncated: %d -> %d chars", len(text), MAX_SOURCE_CHARS
        )
        text = text[:MAX_SOURCE_CHARS]
    return text


def maybe_compress(llm_call: Callable, existing_summary: str, older: list[dict]):
    """增量压缩：已有摘要 + 新滑出窗口的旧消息合并为新摘要。

    返回 (new_summary, usage)；旧消息不足 MIN_COMPRESSIBLE_MESSAGES 或压缩
    结果为空时返回 None。调用方负责 try/except 降级，本函数不吞异常。
    """
    if not older or len(older) < MIN_COMPRESSIBLE_MESSAGES:
        return None

    parts = []
    if existing_summary.strip():
        parts.append("Existing memory:\n" + existing_summary.strip())
    parts.append("New older conversation:\n" + _format_older(older))
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]

    logger.info(
        "memory compression start: older=%d has_existing=%s",
        len(older), bool(existing_summary.strip()),
    )
    result = llm_call(
        messages,
        call_site="chat.memory_compress",
        temperature=COMPRESS_TEMPERATURE,
        max_tokens=COMPRESS_MAX_TOKENS,
    )
    summary = (result.get("content") or "").strip()
    if not summary:
        logger.warning("memory compression returned empty summary, keeping previous")
        return None
    if len(summary) > MAX_SUMMARY_CHARS:
        logger.info("memory summary truncated: %d -> %d chars", len(summary), MAX_SUMMARY_CHARS)
        summary = summary[:MAX_SUMMARY_CHARS]
    usage = result.get("usage")
    logger.info(
        "memory compression done: summary_len=%d total_tokens=%s",
        len(summary), getattr(usage, "total_tokens", 0),
    )
    return summary, usage
