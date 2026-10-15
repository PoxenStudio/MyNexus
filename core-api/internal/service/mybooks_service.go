package service

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"

	"mynexus/core-api/internal/api/dto"
	"mynexus/core-api/internal/config"
)

type MyBooksService struct {
	cfg config.MyBooksConfig
	hc  *http.Client
}

func NewMyBooksService(cfg config.MyBooksConfig) *MyBooksService {
	return &MyBooksService{
		cfg: cfg,
		hc:  &http.Client{Timeout: 30 * time.Second},
	}
}

func (s *MyBooksService) withAuth(req *http.Request) {
	if s.cfg.Username != "" {
		req.Header.Set("Authorization", "Basic "+basicAuth(s.cfg.Username, s.cfg.Password))
	}
}

func basicAuth(u, p string) string {
	return base64.StdEncoding.EncodeToString([]byte(u + ":" + p))
}

func (s *MyBooksService) Test(cfg config.MyBooksConfig) error {
	url := strings.TrimRight(cfg.BaseURL, "/") + "/api/user/info"
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	if cfg.Username != "" {
		req.Header.Set("Authorization", "Basic "+basicAuth(cfg.Username, cfg.Password))
	}
	hc := &http.Client{Timeout: 10 * time.Second}
	resp, err := hc.Do(req)
	if err != nil {
		return fmt.Errorf("connect: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, truncate(string(body), 200))
	}
	var body struct {
		Err string `json:"err"`
	}
	_ = json.NewDecoder(resp.Body).Decode(&body)
	if body.Err != "" && body.Err != "ok" {
		return fmt.Errorf("MyBooks error: %s", body.Err)
	}
	return nil
}

func (s *MyBooksService) Search(name string, start, size int) (dto.MyBooksSearchResponse, error) {
	base := strings.TrimRight(s.cfg.BaseURL, "/")
	u, err := url.Parse(base + "/api/search")
	if err != nil {
		return dto.MyBooksSearchResponse{}, fmt.Errorf("build url: %w", err)
	}
	q := u.Query()
	q.Set("name", name)
	q.Set("start", fmt.Sprintf("%d", start))
	q.Set("size", fmt.Sprintf("%d", size))
	u.RawQuery = q.Encode()

	req, err := http.NewRequest(http.MethodGet, u.String(), nil)
	if err != nil {
		return dto.MyBooksSearchResponse{}, fmt.Errorf("build request: %w", err)
	}
	s.withAuth(req)

	log.Printf("[mybooks] search name=%q start=%d size=%d url=%s", name, start, size, u.String())
	resp, err := s.hc.Do(req)
	if err != nil {
		return dto.MyBooksSearchResponse{}, fmt.Errorf("search MyBooks: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return dto.MyBooksSearchResponse{}, fmt.Errorf("read response: %w", err)
	}
	if resp.StatusCode >= 400 {
		return dto.MyBooksSearchResponse{}, fmt.Errorf("HTTP %d: %s", resp.StatusCode, truncate(string(data), 200))
	}

	var raw struct {
		Err   string `json:"err"`
		Title string `json:"title"`
		Total int    `json:"total"`
		Books []struct {
			ID        int64  `json:"id"`
			Title     string `json:"title"`
			Author    string `json:"author"`
			Authors   any    `json:"authors"`
			Thumb     string `json:"thumb"`
			Img       string `json:"img"`
			Publisher string `json:"publisher"`
			Language  string `json:"language"`
			Languages any    `json:"languages"`
			Tags      any    `json:"tags"`
			Series    string `json:"series"`
			ISBN      string `json:"isbn"`
			PubDate   string `json:"pubdate"`
			Comments  string `json:"comments"`
			Files     []struct {
				Format string `json:"format"`
				Size   int64  `json:"size"`
			} `json:"files"`
		} `json:"books"`
	}
	if err := json.Unmarshal(data, &raw); err != nil {
		return dto.MyBooksSearchResponse{}, fmt.Errorf("parse response: %w", err)
	}
	if raw.Err != "" && raw.Err != "ok" {
		return dto.MyBooksSearchResponse{}, fmt.Errorf("MyBooks error: %s", raw.Err)
	}

	items := make([]dto.MyBooksSearchItem, 0, len(raw.Books))
	for _, b := range raw.Books {
		lang := b.Language
		if lang == "" {
			for _, s := range toStrSlice(b.Languages) {
				lang = s
				break
			}
		}
		authors := toStrSlice(b.Authors)
		if len(authors) == 0 && b.Author != "" {
			authors = []string{b.Author}
		}
		files := make([]dto.MyBooksFileInfo, len(b.Files))
		for i, f := range b.Files {
			files[i] = dto.MyBooksFileInfo{Format: strings.ToLower(f.Format), Size: f.Size}
		}
		items = append(items, dto.MyBooksSearchItem{
			ID:        b.ID,
			Title:     b.Title,
			Author:    b.Author,
			Authors:   authors,
			Thumb:     b.Thumb,
			Img:       b.Img,
			Publisher: b.Publisher,
			Language:  lang,
			Tags:      toStrSlice(b.Tags),
			Series:    b.Series,
			ISBN:      b.ISBN,
			PubDate:   b.PubDate,
			Comments:  b.Comments,
			Files:     files,
		})
	}

	return dto.MyBooksSearchResponse{
		Title: raw.Title,
		Total: raw.Total,
		Start: start,
		Size:  size,
		Books: items,
	}, nil
}

func (s *MyBooksService) DownloadFile(id int64, format string) (io.ReadCloser, error) {
	url := fmt.Sprintf("%s/api/book/%d.%s", strings.TrimRight(s.cfg.BaseURL, "/"), id, strings.ToLower(format))
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("build download request: %w", err)
	}
	s.withAuth(req)

	log.Printf("[mybooks] download book=%d format=%s url=%s", id, format, url)
	hc := &http.Client{Timeout: 120 * time.Second}
	resp, err := hc.Do(req)
	if err != nil {
		return nil, fmt.Errorf("download: %w", err)
	}
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		resp.Body.Close()
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, truncate(string(body), 200))
	}
	return resp.Body, nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n] + "..."
}

func toStrSlice(v any) []string {
	switch x := v.(type) {
	case nil:
		return nil
	case string:
		if x == "" {
			return nil
		}
		return []string{x}
	case []any:
		out := make([]string, 0, len(x))
		for _, e := range x {
			if s, ok := e.(string); ok && s != "" {
				out = append(out, s)
			}
		}
		return out
	case []string:
		out := make([]string, 0, len(x))
		for _, s := range x {
			if s != "" {
				out = append(out, s)
			}
		}
		return out
	default:
		return nil
	}
}
