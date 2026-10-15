package models

type Chapter struct {
	ID        string
	BookID    string
	Title     string
	Level     int
	SortOrder int
	Content   string
	Summary   string
	// Keywords/Definitions/References are raw JSON strings (same storage
	// convention as Book.Keywords) — see dto.NewChapterResponse for the
	// decode side.
	Keywords   string
	Definitions string
	References string
}
