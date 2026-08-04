package models

type Chapter struct {
	ID        string
	BookID    string
	Title     string
	Level     int
	SortOrder int
	Content   string
	Summary   string
}
