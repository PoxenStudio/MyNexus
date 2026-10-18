import logging
import re

from tools.base import BaseTool

logger = logging.getLogger(__name__)

MINDMAP_INTENT_RE = re.compile(r"思维导图|脑图|知识图谱|概念图|mind\s*map|mindmap", re.IGNORECASE)


def wants_mindmap(text: str) -> bool:
    """Whether the user's message explicitly asks for a mindmap. The pipeline
    forces this tool on such turns because the decision call can otherwise
    skip it (see pipelines/qa.py)."""
    return bool(MINDMAP_INTENT_RE.search(text or ""))


class MindmapTool(BaseTool):
    """Pure formatting tool: the model authors title/markdown itself from
    evidence gathered by earlier retrieval tools in the same turn — this
    tool only validates, normalizes mermaid fallback syntax, and computes
    stats."""

    @property
    def name(self) -> str:
        return "generate_mindmap"

    @property
    def description(self) -> str:
        return (
            "生成思维导图可视化。当用户要求生成思维导图、知识图谱、概念图或可视化某本书/某章/某主题的结构时调用。"
            "调用前应先通过 semantic_search/read_chapter/search_by_chapters 获取足够的原文证据，"
            "markdown 必须基于检索到的事实，不得凭空编造。"
            "markdown 参数必须使用标准 Markdown 标题语法（# ## ### 与 - 列表），禁止使用 mermaid mindmap 语法。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "思维导图标题，例如《三国演义》主要人物关系",
                },
                "markdown": {
                    "type": "string",
                    "description": (
                        "思维导图内容，标准 Markdown 标题格式（禁止 mermaid 语法）："
                        "# 为中心主题，## 为主分支，### 为子分支，- 为叶子项。"
                        "每个节点用简洁短语；层次不超过 4 级标题；节点数建议 30-80 个。\n"
                        "示例：\n"
                        "# 主题\n"
                        "## 阵营 A\n"
                        "### 核心人物\n"
                        "- 人物甲（关系说明）\n"
                        "## 阵营 B\n"
                        "- 人物乙"
                    ),
                },
            },
            "required": ["title", "markdown"],
        }

    def run(self, title: str = "", markdown: str = "", **kwargs) -> dict:
        title = (title or "").strip()
        raw = (markdown or "").strip()
        if not title:
            return {"error": "mindmap title is required"}
        if not raw:
            return {"error": "mindmap markdown content is required"}

        if raw.startswith("mindmap") or raw.startswith("```mermaid") or raw.startswith("graph"):
            raw = self._convert_mermaid(raw, title)
            logger.info("mindmap: converted mermaid syntax to markdown headings")

        node_count = len([l for l in raw.split("\n") if l.strip()])
        logger.info("mindmap tool: title=%s nodes=%d", title, node_count)

        return {
            "type": "mindmap",
            "title": title,
            "markdown": raw,
            "stats": {"node_count": node_count},
        }

    _FENCE_RE = re.compile(r"^```(?:mermaid|markdown|md)?\s*|\s*```$", re.MULTILINE)

    def _convert_mermaid(self, text: str, fallback_title: str) -> str:
        text = self._FENCE_RE.sub("", text)
        text = re.sub(r"^(mindmap|graph\s+\w+)\s*$", "", text, flags=re.MULTILINE).strip()
        lines = text.split("\n")

        min_indent = float("inf")
        for line in lines:
            if not line.strip():
                continue
            min_indent = min(min_indent, len(line) - len(line.lstrip()))
        if min_indent == float("inf"):
            min_indent = 0

        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip())
            depth = max(0, (indent - min_indent) // 2)
            clean = stripped
            if "-->" in clean:
                continue
            for pat in (r"^\((.+)\)$", r"^\[(.+)\]$", r"^\{(.+)\}$", r'^["\'](.+)["\']$'):
                m = re.match(pat, clean)
                if m:
                    clean = m.group(1)
                    break

            if depth == 0:
                result.append(f"# {clean}")
            elif depth == 1:
                result.append(f"## {clean}")
            elif depth == 2:
                result.append(f"### {clean}")
            elif depth == 3:
                result.append(f"#### {clean}")
            else:
                result.append(f"{'  ' * max(0, depth - 4)}- {clean}")

        return "\n".join(result) if result else f"# {fallback_title}"
