package models

type Chapter struct {
	ID        string
	BookID    string
	Title     string
	Level     int
	SortOrder int
	Content   string
	Summary   string
	// Keywords/Definitions are raw JSON strings (same storage convention as
	// Book.Keywords) — see dto.NewChapterResponse for the decode side.
	// Keywords is this chapter's own top-N content keywords, distinct from
	// the whole-book aggregate on Book.Keywords. Definitions is a JSON array
	// of {"name","content"} objects, LLM-extracted from the chapter's text
	// (see worker/src/pipelines/summary.py's _extract_chapter_definitions).
	Keywords    string
	Definitions string
}
