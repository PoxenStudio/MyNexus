from dataclasses import dataclass

from tools.base import BaseTool


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    description: str
    parameters: dict
    prompt: str
    version: int = 1


SKILLS = (
    Skill(
        id="concept-explainer",
        name="概念讲解",
        description="深入解释书中的概念、术语或抽象思想，结合原文语境和例子。",
        parameters={
            "type": "object",
            "properties": {
                "concept": {"type": "string", "description": "要解释的概念或术语。"},
                "depth": {
                    "type": "string",
                    "enum": ["simple", "detailed"],
                    "default": "simple",
                    "description": "simple 用直观语言解释；detailed 补充定义、关联概念和书中应用。",
                },
                "book_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["concept"],
            "additionalProperties": False,
        },
        prompt=(
            "解释用户指定的书中概念。先根据提供的书籍片段确定作者在此处的含义，"
            "再按参数深度组织解释，并给出有来源支持的书中应用或例子。"
            "区分原文明确陈述与合理推断；片段不足时说明缺少什么证据，不要把通用知识冒充作者观点。"
        ),
    ),
    Skill(
        id="argument-analyzer",
        name="论证分析",
        description="分析书中主张、支持证据、推理链条和论证结构。",
        parameters={
            "type": "object",
            "properties": {
                "focus_type": {
                    "type": "string",
                    "enum": ["main", "evidence", "structure", "all"],
                    "default": "all",
                },
                "query": {"type": "string", "description": "希望分析的论点或主题。"},
                "book_ids": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
        prompt=(
            "分析作者围绕用户问题提出的论证。识别主张、理由与证据，说明它们之间的推理关系；"
            "按 focus_type 聚焦核心主张、证据、结构或完整分析。"
            "只评价材料实际呈现的逻辑强弱；不要臆造反方观点、事实或作者未表达的结论。"
        ),
    ),
    Skill(
        id="character-tracker",
        name="人物追踪",
        description="跨章节梳理人物信息、关系、关键行动和发展变化。",
        parameters={
            "type": "object",
            "properties": {
                "character_name": {"type": "string", "description": "目标人物；省略时概览主要人物。"},
                "book_ids": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
        prompt=(
            "根据提供的章节材料追踪人物。按时间或章节顺序整理身份、关键行动、关系和变化，"
            "并为重要判断保留对应来源。区分明确事实与解释性推断；不要把同名人物或不同作品的人物混为一谈。"
            "材料只覆盖部分章节时，明确说明追踪范围和信息边界。"
        ),
    ),
    Skill(
        id="quote-collector",
        name="原文摘录",
        description="从书籍原文中筛选有启发性、优美或有争议的引句，并简要说明。",
        parameters={
            "type": "object",
            "properties": {
                "quote_type": {
                    "type": "string",
                    "enum": ["insightful", "beautiful", "controversial", "all"],
                    "default": "all",
                },
                "max_quotes": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 10,
                },
                "book_ids": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
        prompt=(
            "只从提供的原文片段中逐字摘录引句，不得改写后加引号，也不得补全片段中不存在的文字。"
            "按 quote_type 筛选，最多返回 max_quotes 条；每条附简短说明及可用的章节来源。"
            "原文片段被截断或无法确认准确文字时，跳过该引句并说明限制。"
        ),
    ),
    Skill(
        id="reading-guide",
        name="阅读指南",
        description="根据书籍或章节内容生成预习、复习或讨论指南。",
        parameters={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["preview", "review", "discuss"],
                    "default": "discuss",
                },
                "book_ids": {"type": "array", "items": {"type": "string"}},
                "chapter_id": {"type": "string"},
            },
            "additionalProperties": False,
        },
        prompt=(
            "根据提供的书籍摘要和/或原文生成阅读指南。preview 提供内容预览和阅读关注点；"
            "review 回顾核心内容并设计理解检查题；discuss 提出开放讨论问题和可辩论主题。"
            "优先复用已有摘要，再用原文检索结果补充；问题应锚定材料，不要假设读者已知材料未提供的情节或观点。"
        ),
    ),
    Skill(
        id="reference-index",
        name="引用书目汇总",
        description="从书籍原文中识别并统计被引用的书籍或文章，列出出现频次最高的条目。",
        parameters={
            "type": "object",
            "properties": {
                "max_items": {
                    "type": "integer",
                    "minimum": 5,
                    "maximum": 50,
                    "default": 30,
                    "description": "最多返回多少条高频引用条目。",
                },
                "book_ids": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
        prompt=(
            "从提供的书籍原文片段中识别被引用或被提到的外部著作（书名、文章名、论文等），"
            "按出现频次从高到低排序，列出最多 max_items 条。每条包含：引用对象名称、"
            "出现次数、以及一两个代表性的原文出处（章节+摘录短句）。"
            "只统计材料中明确出现过的引用；不要靠作者名或通假推断未出现的条目。"
            "若材料只覆盖一本书的部分章节，在开头说明统计范围和遗漏风险。"
        ),
    ),
)


def validate_parameters(skill: Skill, arguments: dict) -> dict:
    if not isinstance(arguments, dict):
        raise ValueError("skill arguments must be a JSON object")

    schema = skill.parameters
    properties = schema["properties"]
    unknown = arguments.keys() - properties.keys()
    if unknown and schema.get("additionalProperties") is False:
        raise ValueError(f"unexpected parameter(s): {', '.join(sorted(unknown))}")

    validated = dict(arguments)
    for name in schema.get("required", []):
        if name not in validated:
            raise ValueError(f"missing required parameter: {name}")

    for name, value in validated.items():
        definition = properties[name]
        expected_type = definition["type"]
        if expected_type == "string" and not isinstance(value, str):
            raise ValueError(f"{name} must be a string")
        if expected_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(f"{name} must be an integer")
        if expected_type == "array" and (
            not isinstance(value, list) or not all(isinstance(item, str) for item in value)
        ):
            raise ValueError(f"{name} must be an array of strings")
        if "enum" in definition and value not in definition["enum"]:
            raise ValueError(f"{name} must be one of: {', '.join(definition['enum'])}")
        if expected_type == "integer":
            if value < definition.get("minimum", value) or value > definition.get("maximum", value):
                raise ValueError(
                    f"{name} must be between {definition['minimum']} and {definition['maximum']}"
                )

    for name, definition in properties.items():
        if name not in validated and "default" in definition:
            validated[name] = definition["default"]
    return validated


class SkillTool(BaseTool):
    def __init__(self, skill: Skill) -> None:
        self.skill = skill

    @property
    def name(self) -> str:
        return f"skill_{self.skill.id.replace('-', '_')}"

    @property
    def description(self) -> str:
        return self.skill.description

    @property
    def parameters(self) -> dict:
        return self.skill.parameters

    def run(self, **kwargs) -> dict:
        arguments = validate_parameters(self.skill, kwargs)
        return {
            "__skill__": {
                "id": self.skill.id,
                "name": self.skill.name,
                "version": self.skill.version,
                "prompt": self.skill.prompt,
                "arguments": arguments,
            }
        }


def builtin_skill_tools() -> list[SkillTool]:
    return [SkillTool(skill) for skill in SKILLS]
