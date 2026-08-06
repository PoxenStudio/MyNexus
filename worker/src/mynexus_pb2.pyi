from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

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
    def __init__(self, task_id: _Optional[str] = ..., book_id: _Optional[str] = ..., chapters: _Optional[_Iterable[_Union[Chapter, _Mapping]]] = ..., force_restart: bool = ..., language: _Optional[str] = ...) -> None: ...

class SummarizeAck(_message.Message):
    __slots__ = ("accepted",)
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    accepted: bool
    def __init__(self, accepted: bool = ...) -> None: ...

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
    def __init__(self, accepted: bool = ...) -> None: ...

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
    __slots__ = ("chunk_id", "book_id", "chapter_id", "content", "position", "token_count", "score")
    CHUNK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    TOKEN_COUNT_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    chunk_id: str
    book_id: str
    chapter_id: str
    content: str
    position: int
    token_count: int
    score: float
    def __init__(self, chunk_id: _Optional[str] = ..., book_id: _Optional[str] = ..., chapter_id: _Optional[str] = ..., content: _Optional[str] = ..., position: _Optional[int] = ..., token_count: _Optional[int] = ..., score: _Optional[float] = ...) -> None: ...

class SearchResponse(_message.Message):
    __slots__ = ("results",)
    RESULTS_FIELD_NUMBER: _ClassVar[int]
    results: _containers.RepeatedCompositeFieldContainer[SearchResult]
    def __init__(self, results: _Optional[_Iterable[_Union[SearchResult, _Mapping]]] = ...) -> None: ...

class ChatMessage(_message.Message):
    __slots__ = ("role", "content")
    ROLE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    role: str
    content: str
    def __init__(self, role: _Optional[str] = ..., content: _Optional[str] = ...) -> None: ...

class ChatRequest(_message.Message):
    __slots__ = ("messages", "book_ids", "top_k")
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    BOOK_IDS_FIELD_NUMBER: _ClassVar[int]
    TOP_K_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[ChatMessage]
    book_ids: _containers.RepeatedScalarFieldContainer[str]
    top_k: int
    def __init__(self, messages: _Optional[_Iterable[_Union[ChatMessage, _Mapping]]] = ..., book_ids: _Optional[_Iterable[str]] = ..., top_k: _Optional[int] = ...) -> None: ...

class Citation(_message.Message):
    __slots__ = ("chunk_id", "chapter_id", "book_id", "score", "content")
    CHUNK_ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    chunk_id: str
    chapter_id: str
    book_id: str
    score: float
    content: str
    def __init__(self, chunk_id: _Optional[str] = ..., chapter_id: _Optional[str] = ..., book_id: _Optional[str] = ..., score: _Optional[float] = ..., content: _Optional[str] = ...) -> None: ...

class CitationList(_message.Message):
    __slots__ = ("items",)
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Citation]
    def __init__(self, items: _Optional[_Iterable[_Union[Citation, _Mapping]]] = ...) -> None: ...

class ChatChunk(_message.Message):
    __slots__ = ("delta", "citations")
    DELTA_FIELD_NUMBER: _ClassVar[int]
    CITATIONS_FIELD_NUMBER: _ClassVar[int]
    delta: str
    citations: CitationList
    def __init__(self, delta: _Optional[str] = ..., citations: _Optional[_Union[CitationList, _Mapping]] = ...) -> None: ...

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
    def __init__(self, ok: bool = ...) -> None: ...

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
    __slots__ = ("id", "title", "level", "sort_order", "content", "summary")
    ID_FIELD_NUMBER: _ClassVar[int]
    TITLE_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    SORT_ORDER_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    id: str
    title: str
    level: int
    sort_order: int
    content: str
    summary: str
    def __init__(self, id: _Optional[str] = ..., title: _Optional[str] = ..., level: _Optional[int] = ..., sort_order: _Optional[int] = ..., content: _Optional[str] = ..., summary: _Optional[str] = ...) -> None: ...

class Chunk(_message.Message):
    __slots__ = ("id", "chapter_id", "content", "position", "token_count", "vector_id")
    ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    POSITION_FIELD_NUMBER: _ClassVar[int]
    TOKEN_COUNT_FIELD_NUMBER: _ClassVar[int]
    VECTOR_ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    chapter_id: str
    content: str
    position: int
    token_count: int
    vector_id: str
    def __init__(self, id: _Optional[str] = ..., chapter_id: _Optional[str] = ..., content: _Optional[str] = ..., position: _Optional[int] = ..., token_count: _Optional[int] = ..., vector_id: _Optional[str] = ...) -> None: ...

class MetadataRequest(_message.Message):
    __slots__ = ("task_id", "book")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    book: BookMeta
    def __init__(self, task_id: _Optional[str] = ..., book: _Optional[_Union[BookMeta, _Mapping]] = ...) -> None: ...

class CompleteRequest(_message.Message):
    __slots__ = ("task_id", "book", "chapters", "chunks")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_FIELD_NUMBER: _ClassVar[int]
    CHAPTERS_FIELD_NUMBER: _ClassVar[int]
    CHUNKS_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    book: BookMeta
    chapters: _containers.RepeatedCompositeFieldContainer[Chapter]
    chunks: _containers.RepeatedCompositeFieldContainer[Chunk]
    def __init__(self, task_id: _Optional[str] = ..., book: _Optional[_Union[BookMeta, _Mapping]] = ..., chapters: _Optional[_Iterable[_Union[Chapter, _Mapping]]] = ..., chunks: _Optional[_Iterable[_Union[Chunk, _Mapping]]] = ...) -> None: ...

class FailRequest(_message.Message):
    __slots__ = ("task_id", "error_msg")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_MSG_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    error_msg: str
    def __init__(self, task_id: _Optional[str] = ..., error_msg: _Optional[str] = ...) -> None: ...

class ChapterSummaryRequest(_message.Message):
    __slots__ = ("task_id", "chapter_id", "summary")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    CHAPTER_ID_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    chapter_id: str
    summary: str
    def __init__(self, task_id: _Optional[str] = ..., chapter_id: _Optional[str] = ..., summary: _Optional[str] = ...) -> None: ...

class BookSummaryRequest(_message.Message):
    __slots__ = ("task_id", "book_id", "summary", "keywords")
    TASK_ID_FIELD_NUMBER: _ClassVar[int]
    BOOK_ID_FIELD_NUMBER: _ClassVar[int]
    SUMMARY_FIELD_NUMBER: _ClassVar[int]
    KEYWORDS_FIELD_NUMBER: _ClassVar[int]
    task_id: str
    book_id: str
    summary: str
    keywords: _containers.RepeatedCompositeFieldContainer[Keyword]
    def __init__(self, task_id: _Optional[str] = ..., book_id: _Optional[str] = ..., summary: _Optional[str] = ..., keywords: _Optional[_Iterable[_Union[Keyword, _Mapping]]] = ...) -> None: ...

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
