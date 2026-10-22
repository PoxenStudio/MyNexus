import logging
import unicodedata

from grpc_client import CoreApiClient
from tools.base import BaseTool

logger = logging.getLogger(__name__)

_MAX_CONTENT_CHARS = 12000
_MAX_FOCUS_CHARS = 200
_FOCUS_LEAD_CHARS = 800


def _compact_with_positions(text: str) -> tuple[str, list[int]]:
    chars: list[str] = []
    positions: list[int] = []
    for index, char in enumerate(text):
        category = unicodedata.category(char)
        if char.isspace() or category.startswith(("P", "S")):
            continue
        chars.append(char.lower())
        positions.append(index)
    return "".join(chars), positions


def _locate_focus(content: str, focus: str) -> int:
    compact_focus, _ = _compact_with_positions(focus)
    if not compact_focus:
        return -1
    compact_content, positions = _compact_with_positions(content)
    index = compact_content.find(compact_focus)
    if index < 0:
        return -1
    return positions[index]


class ReadChapterTool(BaseTool):
    """Reads one chapter's full cleaned plain text via the CoreApiService
    GetChapterContent RPC — Worker never touches Core API's database directly.
    Backs sequential-reading questions (chapter overview, character relations,
    plot threads) where semantic retrieval is structurally the wrong tool:
    the model needs the chapter's actual running text, not a handful of
    isolated chunks."""

    def __init__(self, core_api: CoreApiClient) -> None:
        self.core_api = core_api

    @property
    def name(self) -> str:
        return "read_chapter"

    @property
    def description(self) -> str:
        return (
            "读取某一章的完整正文。适用于章节级概述、人物关系梳理、情节脉络整理等需要顺序阅读的场景。"
            "chapter_id 需先用 list_chapters 工具获取。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "book_id": {"type": "string", "description": "书籍 id，list_chapters 返回。"},
                "chapter_id": {"type": "string", "description": "章节 id，list_chapters 返回。"},
                "max_chars": {"type": "integer", "default": _MAX_CONTENT_CHARS},
                "focus_text": {
                    "type": "string",
                    "description": "阅读器当前可见的少量原文，用于在超长章节内定位返回窗口。",
                },
            },
            "required": ["book_id", "chapter_id"],
        }

    def run(
        self,
        book_id: str,
        chapter_id: str,
        max_chars: int = _MAX_CONTENT_CHARS,
        focus_text: str = "",
    ) -> dict:
        chapter = self.core_api.get_chapter_content(book_id, chapter_id)
        if chapter is None:
            return {"error": "failed to fetch chapter (not found or core-api unreachable)"}
        full_content = chapter["content"]
        total_chars = len(full_content)
        focus = (focus_text or "").strip()[:_MAX_FOCUS_CHARS]
        start = 0
        if focus:
            offset = _locate_focus(full_content, focus)
            if offset >= 0:
                start = max(0, offset - _FOCUS_LEAD_CHARS)
                logger.info(
                    "read_chapter focus located: chapter=%s offset=%d start=%d focus_len=%d",
                    chapter["chapter_id"], offset, start, len(focus),
                )
            else:
                logger.warning(
                    "read_chapter focus not found: chapter=%s focus_len=%d",
                    chapter["chapter_id"], len(focus),
                )
        end = min(total_chars, start + max(int(max_chars), 1))
        content = full_content[start:end]
        truncated = end < total_chars
        return {
            "book_id": book_id,
            "chapter_id": chapter["chapter_id"],
            "title": chapter["title"],
            "sort_order": chapter["sort_order"],
            "content": content,
            "total_chars": total_chars,
            "truncated": truncated,
            "start_offset": start,
            "end_offset": end,
            "__citations": [
                {
                    "chunk_id": "",
                    "chapter_id": chapter["chapter_id"],
                    "book_id": book_id,
                    "score": 1.0,
                    "content": f"《{chapter['title']}》正文（{start}-{end}）",
                    "start_offset": start,
                    "end_offset": end,
                }
            ],
        }
