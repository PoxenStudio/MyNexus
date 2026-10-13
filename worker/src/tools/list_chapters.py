from grpc_client import CoreApiClient
from tools.base import BaseTool

_MAX_CHAPTERS = 30


class ListChaptersTool(BaseTool):
    """Lists a book's chapter structure (chapter_id/title/sort_order, no
    summaries) so the model can pick which chapters to read_chapter on for
    sequential-reading questions. Lighter than get_book_info, which returns
    the whole metadata + summary payload."""

    def __init__(self, core_api: CoreApiClient) -> None:
        self.core_api = core_api

    @property
    def name(self) -> str:
        return "list_chapters"

    @property
    def description(self) -> str:
        return (
            "列出某本书的章节目录（章节 id、标题、顺序），不带摘要。适用于概述全书前先看结构、"
            "决定读哪些章。返回的 chapter_id 可传给 read_chapter 读取正文。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "书名或书名关键词，用于在书库中定位书籍。"},
                "limit": {"type": "integer", "default": _MAX_CHAPTERS},
            },
            "required": ["query"],
        }

    def run(self, query: str, limit: int = _MAX_CHAPTERS) -> dict:
        books = self.core_api.get_book_info(query)
        if books is None:
            return {"error": "failed to reach core-api for chapter list"}
        if not books:
            return {"error": f"no book found matching {query!r}"}
        items = []
        for b in books:
            chapters = [
                {"chapter_id": c["chapter_id"], "title": c["title"], "sort_order": c["sort_order"]}
                for c in b["chapters"][:limit]
            ]
            items.append(
                {
                    "book_id": b["book_id"],
                    "title": b["title"],
                    "author": b["author"],
                    "chapters": chapters,
                    "total_chapters": len(b["chapters"]),
                    "returned": len(chapters),
                }
            )
        return {"books": items}
