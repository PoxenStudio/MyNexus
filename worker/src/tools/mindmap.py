import logging
import re

from nodes.llm.base_llm import BaseLLM
from pipelines.retrieval import RetrievalPipeline
from tools.base import BaseTool

logger = logging.getLogger(__name__)

_MINDMAP_PROMPT = """你是思维导图生成助手。根据以下书籍内容，生成一个结构清晰的思维导图，使用标准 Markdown 标题格式：
- 一级标题 (#) 作为根节点（思维导图的中心主题）
- 二级标题 (##) 作为主要分支
- 三级标题 (###) 作为子分支
- 无序列表项 (-) 作为叶子节点/具体细节

规则：
1. 根节点使用书籍标题或主题
2. 从粗到细，层次不超过 4 级标题
3. 内容要忠实于参考材料，不要凭空添加
4. 每个节点用简洁的短语，不用长句

参考内容：
{context}

请输出思维导图 Markdown："""


class MindmapTool(BaseTool):

    def __init__(self, retrieval: RetrievalPipeline, llm: BaseLLM) -> None:
        self.retrieval = retrieval
        self.llm = llm

    @property
    def name(self) -> str:
        return "generate_mindmap"

    @property
    def description(self) -> str:
        return (
            "根据书籍内容生成思维导图。当用户要求生成思维导图、知识图谱、概念图、"
            "或者可视化某本书/某章/某个主题的结构时调用此工具。"
            "工具内部会检索相关书籍内容并生成思维导图的 Markdown 结构。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要生成思维导图的主题描述，用于检索相关书籍内容。例如「《活着》的主要人物和情节」",
                },
            },
            "required": ["query"],
        }

    def run(self, query: str = "", **kwargs) -> dict:
        search_query = query or "思维导图 主要内容 章节结构"
        results = self.retrieval.search(search_query, top_k=15)
        if not results:
            return {"error": "未检索到相关书籍内容，无法生成思维导图"}

        citations = [
            {
                "chunk_id": r["id"],
                "chapter_id": r["chapter_id"],
                "book_id": r["book_id"],
                "score": r["score"],
                "content": r["content"][:200],
            }
            for r in results
        ]

        context = "\n\n".join(f"[片段 {i + 1}]\n{r['content']}" for i, r in enumerate(results))
        messages = [{"role": "system", "content": _MINDMAP_PROMPT.format(context=context)}]

        chunks = []
        try:
            for delta in self.llm.process(messages, call_site="qa.mindmap"):
                chunks.append(delta)
        except Exception as exc:
            logger.exception("mindmap llm generation failed")
            return {"error": f"思维导图生成失败: {exc}"}

        markdown = "".join(chunks).strip()
        markdown = self._clean_markdown(markdown)
        title = self._extract_title(markdown)

        node_count = len([l for l in markdown.split("\n") if l.strip()])
        logger.info("mindmap generated: title=%s nodes=%d", title, node_count)

        return {
            "type": "mindmap",
            "title": title,
            "markdown": markdown,
            "stats": {"node_count": node_count},
            "__citations": citations,
        }

    _FENCE_RE = re.compile(r"^```(?:markdown|md|mermaid)?\s*|\s*```$", re.MULTILINE)
    _MERMAID_RE = re.compile(r"^mindmap\s*$", re.MULTILINE)

    def _clean_markdown(self, text: str) -> str:
        text = self._FENCE_RE.sub("", text).strip()
        if text.startswith("mindmap") or text.startswith("graph"):
            text = self._convert_mermaid(text)
        return text

    def _extract_title(self, markdown: str) -> str:
        for line in markdown.split("\n"):
            stripped = line.strip()
            m = re.match(r"^#\s+(.+)", stripped)
            if m:
                return m.group(1).strip()
        return "思维导图"

    def _convert_mermaid(self, text: str) -> str:
        text = self._MERMAID_RE.sub("", text).strip()
        lines = text.split("\n")

        min_indent = float("inf")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip())
            min_indent = min(min_indent, indent)
        if min_indent == float("inf"):
            min_indent = 0

        result: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip())
            depth = (indent - min_indent) // 2
            clean = stripped
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
                list_indent = "  " * max(0, depth - 4)
                result.append(f"{list_indent}- {clean}")

        return "\n".join(result) if result else "# 思维导图"
