package models

type Chunk struct {
	ID         string
	ChapterID  string
	BookID     string
	Content    string
	TokenCount int
	Position   int
	VectorID   string
	Keywords   string // JSON array, stored as-is
}
