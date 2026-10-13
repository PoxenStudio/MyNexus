from grpc_client import CoreApiClient
from tools.base import BaseTool

_MAX_CONTENT_CHARS = 12000


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
            },
            "required": ["book_id", "chapter_id"],
        }

    def run(self, book_id: str, chapter_id: str, max_chars: int = _MAX_CONTENT_CHARS) -> dict:
        chapter = self.core_api.get_chapter_content(book_id, chapter_id)
        if chapter is None:
            return {"error": "failed to fetch chapter (not found or core-api unreachable)"}
        content = chapter["content"]
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]
        return {
            "book_id": book_id,
            "chapter_id": chapter["chapter_id"],
            "title": chapter["title"],
            "sort_order": chapter["sort_order"],
            "content": content,
            "total_chars": len(chapter["content"]),
            "truncated": truncated,
            "start_offset": 0,
            "end_offset": len(content),
            "__citations": [
                {
                    "chunk_id": "",
                    "chapter_id": chapter["chapter_id"],
                    "book_id": book_id,
                    "score": 1.0,
                    "content": f"《{chapter['title']}》整章正文",
                    "start_offset": 0,
                    "end_offset": len(content),
                }
            ],
        }
