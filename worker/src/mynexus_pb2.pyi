from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class VectorBookRequest(_message.Message):
    __slots__ = ("book_id",)
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    book_id: str
    def __init__(self, book_id: _Optional[str] = ...) -> None: ...

class VectorRecord(_message.Message):
    __slots__ = ("id", "book_id", "chapter_id", "content", "position", "token_count", "start_offset", "end_offset", "embedding")
    ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    TOKEN_COUNT_FIELD_NUMBER: _ClassVar[int]
    START_OFFSET_FIELD_NUMBER: _ClassVar[int]
    END_OFFSET_FIELD_NUMBER: _ClassVar[int]
    EMBEDDING_FIELD_NUMBER: _ClassVar[int]
    id: str
    book_id: str
    chapter_id: str
    content: str
    position: int
    token_count: int
    start_offset: int
    end_offset: int
    embedding: _containers.RepeatedScalarFieldContainer[float]
    def __init__(self, id: _Optional[str] = ..., book_id: _Optional[str] = ..., chapter_id: _Optional[str] = ..., content: _Optional[str] = ..., position: _Optional[int] = ..., token_count: _Optional[int] = ..., start_offset: _Optional[int] = ..., end_offset: _Optional[int] = ..., embedding: _Optional[_Iterable[float]] = ...) -> None: ...

class CommitBookVectorImportRequest(_message.Message):
    __slots__ = ("book_id", "staging_book_id", "backup_book_id")
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    STAGING_BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    BACKUP_BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    book_id: str
    staging_book_id: str
    backup_book_id: str
    def __init__(self, book_id: _Optional[str] = ..., staging_book_id: _Optional[str] = ..., backup_book_id: _Optional[str] = ...) -> None: ...

class RollbackBookVectorImportRequest(_message.Message):
    __slots__ = ("book_id", "staging_book_id", "backup_book_id")
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    STAGING_BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    BACKUP_BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    book_id: str
    staging_book_id: str
    backup_book_id: str
    def __init__(self, book_id: _Optional[str] = ..., staging_book_id: _Optional[str] = ..., backup_book_id: _Optional[str] = ...) -> None: ...

class FinalizeBookVectorImportRequest(_message.Message):
    __slots__ = ("staging_book_id", "backup_book_id")
    STAGING_BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    BACKUP_BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    staging_book_id: str
    backup_book_id: str
    def __init__(self, staging_book_id: _Optional[str] = ..., backup_book_id: _Optional[str] = ...) -> None: ...

class CancelTaskRequest(_message.Message):
    __slots__ = ("task_id",)
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    def __init__(self, task_id: _Optional[str] = ...) -> None: ...

class ReembedBookSummaryRequest(_message.Message):
    __slots__ = ("book_id", "summary")
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    book_id: str
    summary: str
    def __init__(self, book_id: _Optional[str] = ..., summary: _Optional[str] = ...) -> None: ...

class DeleteBookRequest(_message.Message):
    __slots__ = ("book_id",)
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    book_id: str
    def __init__(self, book_id: _Optional[str] = ...) -> None: ...

class ShutdownRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SummarizeRequest(_message.Message):
    __slots__ = ("task_id", "book_id", "chapters", "force_restart", "language")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTERS_FIELD_NUMBER: _ClassVar[int]
    FORCE_RESTART_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    book_id: str
    chapters: _containers.RepeatedCompositeFieldContainer[Chapter]
    force_restart: bool
    language: str
    def __init__(self, task_id: _Optional[str] = ..., book_id: _Optional[str] = ..., chapters: _Optional[_Iterable[_Union[Chapter, _Mapping]]] = ..., force_restart: _Optional[bool] = ..., language: _Optional[str] = ...) -> None: ...

class SummarizeAck(_message.Message):
    __slots__ = ("accepted",)
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    accepted: bool
    def __init__(self, accepted: _Optional[bool] = ...) -> None: ...

class IngestRequest(_message.Message):
    __slots__ = ("task_id", "book_id", "file_path", "original_filename")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    FILE_PATH_FIELD_NUMBER: _ClassVar[int]
    ORIGINAL_FILENAME_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    book_id: str
    file_path: str
    original_filename: str
    def __init__(self, task_id: _Optional[str] = ..., book_id: _Optional[str] = ..., file_path: _Optional[str] = ..., original_filename: _Optional[str] = ...) -> None: ...

class IngestAck(_message.Message):
    __slots__ = ("accepted",)
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    accepted: bool
    def __init__(self, accepted: _Optional[bool] = ...) -> None: ...

class SearchRequest(_message.Message):
    __slots__ = ("query", "book_ids", "top_k", "score_threshold")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    BOOK_IDS_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    SCORE_THRESHOLD_FIELD_NUMBER: _ClassVar[int]
    query: str
    book_ids: _containers.RepeatedScalarFieldContainer[str]
    top_k: int
    score_threshold: float
    def __init__(self, query: _Optional[str] = ..., book_ids: _Optional[_Iterable[str]] = ..., top_k: _Optional[int] = ..., score_threshold: _Optional[float] = ...) -> None: ...

class SearchResult(_message.Message):
    __slots__ = ("chunk_id", "book_id", "chapter_id", "content", "position", "token_count", "score", "start_offset", "end_offset")
    CHUNK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    TOKEN_COUNT_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    START_OFFSET_FIELD_NUMBER: _ClassVar[int]
    END_OFFSET_FIELD_NUMBER: _ClassVar[int]
    chunk_id: str
    book_id: str
    chapter_id: str
    content: str
    position: int
    token_count: int
    score: float
    start_offset: int
    end_offset: int
    def __init__(self, chunk_id: _Optional[str] = ..., book_id: _Optional[str] = ..., chapter_id: _Optional[str] = ..., content: _Optional[str] = ..., position: _Optional[int] = ..., token_count: _Optional[int] = ..., score: _Optional[float] = ..., start_offset: _Optional[int] = ..., end_offset: _Optional[int] = ...) -> None: ...

class SearchResponse(_message.Message):
    __slots__ = ("results",)
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[SearchResult]
    def __init__(self, results: _Optional[_Iterable[_Union[SearchResult, _Mapping]]] = ...) -> None: ...

class ReadingContext(_message.Message):
    __slots__ = ("book_title", "chapter_title", "chapter_href", "section_index", "progress_fraction", "page", "cfi")
    BOOK_TITLE_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_TITLE_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_HREF_FIELD_NUMBER: _ClassVar[int]
    SECTION_INDEX_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FRACTION_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    CFI_FIELD_NUMBER: _ClassVar[int]
    book_title: str
    chapter_title: str
    chapter_href: str
    section_index: int
    progress_fraction: float
    page: int
    cfi: str
    def __init__(self, book_title: _Optional[str] = ..., chapter_title: _Optional[str] = ..., chapter_href: _Optional[str] = ..., section_index: _Optional[int] = ..., progress_fraction: _Optional[float] = ..., page: _Optional[int] = ..., cfi: _Optional[str] = ...) -> None: ...

class SelectionContext(_message.Message):
    __slots__ = ("text", "chapter_title", "chapter_href", "section_index", "page", "progress_fraction", "cfi")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_TITLE_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_HREF_FIELD_NUMBER: _ClassVar[int]
    SECTION_INDEX_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FRACTION_FIELD_NUMBER: _ClassVar[int]
    CFI_FIELD_NUMBER: _ClassVar[int]
    text: str
    chapter_title: str
    chapter_href: str
    section_index: int
    page: int
    progress_fraction: float
    cfi: str
    def __init__(self, text: _Optional[str] = ..., chapter_title: _Optional[str] = ..., chapter_href: _Optional[str] = ..., section_index: _Optional[int] = ..., page: _Optional[int] = ..., progress_fraction: _Optional[float] = ..., cfi: _Optional[str] = ...) -> None: ...

class MessageContext(_message.Message):
    __slots__ = ("reading", "selection")
    READING_FIELD_NUMBER: _ClassVar[int]
    SELECTION_FIELD_NUMBER: _ClassVar[int]
    reading: ReadingContext
    selection: SelectionContext
    def __init__(self, reading: _Optional[_Union[ReadingContext, _Mapping]] = ..., selection: _Optional[_Union[SelectionContext, _Mapping]] = ...) -> None: ...

class ChatMessage(_message.Message):
    __slots__ = ("role", "content", "context")
    ROLE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_FIELD_NUMBER: _ClassVar[int]
    role: str
    content: str
    context: MessageContext
    def __init__(self, role: _Optional[str] = ..., content: _Optional[str] = ..., context: _Optional[_Union[MessageContext, _Mapping]] = ...) -> None: ...

class ChatRequest(_message.Message):
    __slots__ = ("messages", "book_ids", "top_k", "memory_summary", "memory_message_count", "older_messages")
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    BOOK_IDS_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    MEMORY_SUMMARY_FIELD_NUMBER: _ClassVar[int]
    MEMORY_MESSAGE_COUNT_FIELD_NUMBER: _ClassVar[int]
    OLDER_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[ChatMessage]
    book_ids: _containers.RepeatedScalarFieldContainer[str]
    top_k: int
    memory_summary: str
    memory_message_count: int
    older_messages: _containers.RepeatedCompositeFieldContainer[ChatMessage]
    def __init__(self, messages: _Optional[_Iterable[_Union[ChatMessage, _Mapping]]] = ..., book_ids: _Optional[_Iterable[str]] = ..., top_k: _Optional[int] = ..., memory_summary: _Optional[str] = ..., memory_message_count: _Optional[int] = ..., older_messages: _Optional[_Iterable[_Union[ChatMessage, _Mapping]]] = ...) -> None: ...

class Citation(_message.Message):
    __slots__ = ("chunk_id", "chapter_id", "book_id", "score", "content", "start_offset", "end_offset")
    CHUNK_ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    START_OFFSET_FIELD_NUMBER: _ClassVar[int]
    END_OFFSET_FIELD_NUMBER: _ClassVar[int]
    chunk_id: str
    chapter_id: str
    book_id: str
    score: float
    content: str
    start_offset: int
    end_offset: int
    def __init__(self, chunk_id: _Optional[str] = ..., chapter_id: _Optional[str] = ..., book_id: _Optional[str] = ..., score: _Optional[float] = ..., content: _Optional[str] = ..., start_offset: _Optional[int] = ..., end_offset: _Optional[int] = ...) -> None: ...

class CitationList(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Citation]
    def __init__(self, items: _Optional[_Iterable[_Union[Citation, _Mapping]]] = ...) -> None: ...

class ToolResult(_message.Message):
    __slots__ = ("tool_name", "result_json")
    TOOL_NAME_FIELD_NUMBER: _ClassVar[int]
    RESULT_JSON_FIELD_NUMBER: _ClassVar[int]
    tool_name: str
    result_json: str
    def __init__(self, tool_name: _Optional[str] = ..., result_json: _Optional[str] = ...) -> None: ...

class MemoryUpdate(_message.Message):
    __slots__ = ("summary", "message_count")
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_COUNT_FIELD_NUMBER: _ClassVar[int]
    summary: str
    message_count: int
    def __init__(self, summary: _Optional[str] = ..., message_count: _Optional[int] = ...) -> None: ...

class ChatChunk(_message.Message):
    __slots__ = ("delta", "citations", "tool_result", "memory_update")
    DELTA_FIELD_NUMBER: _ClassVar[int]
    CITATIONS_FIELD_NUMBER: _ClassVar[int]
    TOOL_RESULT_FIELD_NUMBER: _ClassVar[int]
    MEMORY_UPDATE_FIELD_NUMBER: _ClassVar[int]
    delta: str
    citations: CitationList
    tool_result: ToolResult
    memory_update: MemoryUpdate
    def __init__(self, delta: _Optional[str] = ..., citations: _Optional[_Union[CitationList, _Mapping]] = ..., tool_result: _Optional[_Union[ToolResult, _Mapping]] = ..., memory_update: _Optional[_Union[MemoryUpdate, _Mapping]] = ...) -> None: ...

class ChapterSummariesRequest(_message.Message):
    __slots__ = ("book_id",)
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    book_id: str
    def __init__(self, book_id: _Optional[str] = ...) -> None: ...

class ChapterSummaryEntry(_message.Message):
    __slots__ = ("chapter_id", "summary")
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    chapter_id: str
    summary: str
    def __init__(self, chapter_id: _Optional[str] = ..., summary: _Optional[str] = ...) -> None: ...

class ChapterSummariesResponse(_message.Message):
    __slots__ = ("chapters", "book_summary")
    CHAPTERS_FIELD_NUMBER: _ClassVar[int]
    BOOK_SUMMARY_FIELD_NUMBER: _ClassVar[int]
    chapters: _containers.RepeatedCompositeFieldContainer[ChapterSummaryEntry]
    book_summary: str
    def __init__(self, chapters: _Optional[_Iterable[_Union[ChapterSummaryEntry, _Mapping]]] = ..., book_summary: _Optional[str] = ...) -> None: ...

class ProgressRequest(_message.Message):
    __slots__ = ("task_id", "progress", "stage", "message")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    PROGRESS_FIELD_NUMBER: _ClassVar[int]
    STAGE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    progress: int
    stage: str
    message: str
    def __init__(self, task_id: _Optional[str] = ..., progress: _Optional[int] = ..., stage: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class Ack(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: _Optional[bool] = ...) -> None: ...

class BookMeta(_message.Message):
    __slots__ = ("title", "author", "language")
    TITLE_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    title: str
    author: str
    language: str
    def __init__(self, title: _Optional[str] = ..., author: _Optional[str] = ..., language: _Optional[str] = ...) -> None: ...

class Chapter(_message.Message):
    __slots__ = ("id", "title", "level", "sort_order", "content", "summary", "keywords", "references")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    KEYWORDS_FIELD_NUMBER: _ClassVar[int]
    REFERENCES_FIELD_NUMBER: _ClassVar[int]
    id: str
    title: str
    level: int
    sort_order: int
    content: str
    summary: str
    keywords: _containers.RepeatedCompositeFieldContainer[Keyword]
    references: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, id: _Optional[str] = ..., title: _Optional[str] = ..., level: _Optional[int] = ..., sort_order: _Optional[int] = ..., content: _Optional[str] = ..., summary: _Optional[str] = ..., keywords: _Optional[_Iterable[_Union[Keyword, _Mapping]]] = ..., references: _Optional[_Iterable[str]] = ...) -> None: ...

class Chunk(_message.Message):
    __slots__ = ("id", "chapter_id", "content", "position", "token_count", "vector_id", "start_offset", "end_offset")
    ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    TOKEN_COUNT_FIELD_NUMBER: _ClassVar[int]
    VECTOR_ID_FIELD_NUMBER: _ClassVar[int]
    START_OFFSET_FIELD_NUMBER: _ClassVar[int]
    END_OFFSET_FIELD_NUMBER: _ClassVar[int]
    id: str
    chapter_id: str
    content: str
    position: int
    token_count: int
    vector_id: str
    start_offset: int
    end_offset: int
    def __init__(self, id: _Optional[str] = ..., chapter_id: _Optional[str] = ..., content: _Optional[str] = ..., position: _Optional[int] = ..., token_count: _Optional[int] = ..., vector_id: _Optional[str] = ..., start_offset: _Optional[int] = ..., end_offset: _Optional[int] = ...) -> None: ...

class MetadataRequest(_message.Message):
    __slots__ = ("task_id", "book")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    book: BookMeta
    def __init__(self, task_id: _Optional[str] = ..., book: _Optional[_Union[BookMeta, _Mapping]] = ...) -> None: ...

class CompleteRequest(_message.Message):
    __slots__ = ("task_id", "book", "chapters", "chunks", "cover", "cover_content_type")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_FIELD_NUMBER: _ClassVar[int]
    CHAPTERS_FIELD_NUMBER: _ClassVar[int]
    CHUNKS_FIELD_NUMBER: _ClassVar[int]
    COVER_FIELD_NUMBER: _ClassVar[int]
    COVER_CONTENT_TYPE_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    book: BookMeta
    chapters: _containers.RepeatedCompositeFieldContainer[Chapter]
    chunks: _containers.RepeatedCompositeFieldContainer[Chunk]
    cover: bytes
    cover_content_type: str
    def __init__(self, task_id: _Optional[str] = ..., book: _Optional[_Union[BookMeta, _Mapping]] = ..., chapters: _Optional[_Iterable[_Union[Chapter, _Mapping]]] = ..., chunks: _Optional[_Iterable[_Union[Chunk, _Mapping]]] = ..., cover: _Optional[bytes] = ..., cover_content_type: _Optional[str] = ...) -> None: ...

class FailRequest(_message.Message):
    __slots__ = ("task_id", "error_msg", "canceled")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_MSG_FIELD_NUMBER: _ClassVar[int]
    CANCELED_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    error_msg: str
    canceled: bool
    def __init__(self, task_id: _Optional[str] = ..., error_msg: _Optional[str] = ..., canceled: _Optional[bool] = ...) -> None: ...

class ChapterSummaryRequest(_message.Message):
    __slots__ = ("task_id", "chapter_id", "summary", "keywords", "definitions", "references")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    KEYWORDS_FIELD_NUMBER: _ClassVar[int]
    DEFINITIONS_FIELD_NUMBER: _ClassVar[int]
    REFERENCES_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    chapter_id: str
    summary: str
    keywords: _containers.RepeatedCompositeFieldContainer[Keyword]
    definitions: _containers.RepeatedCompositeFieldContainer[Definition]
    references: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, task_id: _Optional[str] = ..., chapter_id: _Optional[str] = ..., summary: _Optional[str] = ..., keywords: _Optional[_Iterable[_Union[Keyword, _Mapping]]] = ..., definitions: _Optional[_Iterable[_Union[Definition, _Mapping]]] = ..., references: _Optional[_Iterable[str]] = ...) -> None: ...

class Definition(_message.Message):
    __slots__ = ("name", "content")
    NAME_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    name: str
    content: str
    def __init__(self, name: _Optional[str] = ..., content: _Optional[str] = ...) -> None: ...

class BookSummaryRequest(_message.Message):
    __slots__ = ("task_id", "book_id", "summary", "keywords", "reading_guide", "reference_index")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    KEYWORDS_FIELD_NUMBER: _ClassVar[int]
    READING_GUIDE_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_INDEX_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    book_id: str
    summary: str
    keywords: _containers.RepeatedCompositeFieldContainer[Keyword]
    reading_guide: str
    reference_index: str
    def __init__(self, task_id: _Optional[str] = ..., book_id: _Optional[str] = ..., summary: _Optional[str] = ..., keywords: _Optional[_Iterable[_Union[Keyword, _Mapping]]] = ..., reading_guide: _Optional[str] = ..., reference_index: _Optional[str] = ...) -> None: ...

class TokenUsageRequest(_message.Message):
    __slots__ = ("task_id", "book_id", "task_type", "llm_provider", "llm_model", "call_site", "prompt_tokens", "completion_tokens", "total_tokens")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    TASK_TYPE_FIELD_NUMBER: _ClassVar[int]
    LLM_PROVIDER_FIELD_NUMBER: _ClassVar[int]
    LLM_MODEL_FIELD_NUMBER: _ClassVar[int]
    CALL_SITE_FIELD_NUMBER: _ClassVar[int]
    PROMPT_TOKENS_FIELD_NUMBER: _ClassVar[int]
    COMPLETION_TOKENS_FIELD_NUMBER: _ClassVar[int]
    TOTAL_TOKENS_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    book_id: str
    task_type: str
    llm_provider: str
    llm_model: str
    call_site: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    def __init__(self, task_id: _Optional[str] = ..., book_id: _Optional[str] = ..., task_type: _Optional[str] = ..., llm_provider: _Optional[str] = ..., llm_model: _Optional[str] = ..., call_site: _Optional[str] = ..., prompt_tokens: _Optional[int] = ..., completion_tokens: _Optional[int] = ..., total_tokens: _Optional[int] = ...) -> None: ...

class Keyword(_message.Message):
    __slots__ = ("term", "weight")
    TERM_FIELD_NUMBER: _ClassVar[int]
    WEIGHT_FIELD_NUMBER: _ClassVar[int]
    term: str
    weight: float
    def __init__(self, term: _Optional[str] = ..., weight: _Optional[float] = ...) -> None: ...

class KeywordSearchRequest(_message.Message):
    __slots__ = ("query", "book_ids", "top_k")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    BOOK_IDS_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    query: str
    book_ids: _containers.RepeatedScalarFieldContainer[str]
    top_k: int
    def __init__(self, query: _Optional[str] = ..., book_ids: _Optional[_Iterable[str]] = ..., top_k: _Optional[int] = ...) -> None: ...

class KeywordSearchResult(_message.Message):
    __slots__ = ("chunk_id", "book_id", "score")
    CHUNK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    chunk_id: str
    book_id: str
    score: float
    def __init__(self, chunk_id: _Optional[str] = ..., book_id: _Optional[str] = ..., score: _Optional[float] = ...) -> None: ...

class KeywordSearchResponse(_message.Message):
    __slots__ = ("results",)
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[KeywordSearchResult]
    def __init__(self, results: _Optional[_Iterable[_Union[KeywordSearchResult, _Mapping]]] = ...) -> None: ...

class LibraryStatsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class BookStatusCount(_message.Message):
    __slots__ = ("status", "count")
    STATUS_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    status: str
    count: int
    def __init__(self, status: _Optional[str] = ..., count: _Optional[int] = ...) -> None: ...

class LibraryStatsResponse(_message.Message):
    __slots__ = ("total_books", "by_status")
    TOTAL_BOOKS_FIELD_NUMBER: _ClassVar[int]
    BY_STATUS_FIELD_NUMBER: _ClassVar[int]
    total_books: int
    by_status: _containers.RepeatedCompositeFieldContainer[BookStatusCount]
    def __init__(self, total_books: _Optional[int] = ..., by_status: _Optional[_Iterable[_Union[BookStatusCount, _Mapping]]] = ...) -> None: ...

class BookInfoRequest(_message.Message):
    __slots__ = ("query", "book_id")
    QUERY_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    query: str
    book_id: str
    def __init__(self, query: _Optional[str] = ..., book_id: _Optional[str] = ...) -> None: ...

class ChapterContentRequest(_message.Message):
    __slots__ = ("book_id", "chapter_id")
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    book_id: str
    chapter_id: str
    def __init__(self, book_id: _Optional[str] = ..., chapter_id: _Optional[str] = ...) -> None: ...

class ChapterContentResponse(_message.Message):
    __slots__ = ("chapter_id", "title", "content", "sort_order")
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    chapter_id: str
    title: str
    content: str
    sort_order: int
    def __init__(self, chapter_id: _Optional[str] = ..., title: _Optional[str] = ..., content: _Optional[str] = ..., sort_order: _Optional[int] = ...) -> None: ...

class ChapterInfo(_message.Message):
    __slots__ = ("chapter_id", "title", "summary", "sort_order")
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    chapter_id: str
    title: str
    summary: str
    sort_order: int
    def __init__(self, chapter_id: _Optional[str] = ..., title: _Optional[str] = ..., summary: _Optional[str] = ..., sort_order: _Optional[int] = ...) -> None: ...

class BookInfo(_message.Message):
    __slots__ = ("book_id", "title", "author", "publisher", "category", "tags", "summary", "chapters")
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    AUTHOR_FIELD_NUMBER: _ClassVar[int]
    PUBLISHER_FIELD_NUMBER: _ClassVar[int]
    CATEGORY_FIELD_NUMBER: _ClassVar[int]
    TAGS_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    CHAPTERS_FIELD_NUMBER: _ClassVar[int]
    book_id: str
    title: str
    author: str
    publisher: str
    category: str
    tags: _containers.RepeatedScalarFieldContainer[str]
    summary: str
    chapters: _containers.RepeatedCompositeFieldContainer[ChapterInfo]
    def __init__(self, book_id: _Optional[str] = ..., title: _Optional[str] = ..., author: _Optional[str] = ..., publisher: _Optional[str] = ..., category: _Optional[str] = ..., tags: _Optional[_Iterable[str]] = ..., summary: _Optional[str] = ..., chapters: _Optional[_Iterable[_Union[ChapterInfo, _Mapping]]] = ...) -> None: ...

class BookInfoResponse(_message.Message):
    __slots__ = ("books",)
    BOOKS_FIELD_NUMBER: _ClassVar[int]
    books: _containers.RepeatedCompositeFieldContainer[BookInfo]
    def __init__(self, books: _Optional[_Iterable[_Union[BookInfo, _Mapping]]] = ...) -> None: ...
