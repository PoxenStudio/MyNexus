package dto

type MyBooksFileInfo struct {
	Format string `json:"format"`
	Size   int64  `json:"size"`
}

type MyBooksSearchItem struct {
	ID        int64             `json:"id"`
	Title     string            `json:"title"`
	Author    string            `json:"author"`
	Authors   []string          `json:"authors"`
	Thumb     string            `json:"thumb"`
	Img       string            `json:"img"`
	Publisher string            `json:"publisher"`
	Language  string            `json:"language"`
	Tags      []string          `json:"tags"`
	Series    string            `json:"series"`
	ISBN      string            `json:"isbn"`
	PubDate   string            `json:"pubdate"`
	Comments  string            `json:"comments"`
	Files     []MyBooksFileInfo `json:"files"`
}

type MyBooksSearchResponse struct {
	Title string              `json:"title"`
	Total int                 `json:"total"`
	Start int                 `json:"start"`
	Size  int                 `json:"size"`
	Books []MyBooksSearchItem `json:"books"`
}

type MyBooksTestRequest struct {
	BaseURL  string `json:"base_url"`
	Username string `json:"username"`
	Password string `json:"password"`
}

type MyBooksImportRequest struct {
	MyBooksID int64  `json:"mybooks_id" binding:"required"`
	Format    string `json:"format" binding:"required,oneof=epub txt"`
}

type MyBooksImportResponse struct {
	BookID string `json:"book_id"`
	TaskID string `json:"task_id"`
}
