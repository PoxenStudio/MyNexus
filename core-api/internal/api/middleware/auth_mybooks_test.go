package middleware

import (
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/gin-gonic/gin"

	"mynexus/core-api/internal/auth"
	"mynexus/core-api/internal/service"
	"mynexus/core-api/internal/storage/sqlite"
)

func TestRequireAuthMapsMyBooksUserForStaticTokenChat(t *testing.T) {
	gin.SetMode(gin.TestMode)
	t.Setenv("MYNEXUS_API_TOKEN", "integration-secret")

	store, err := sqlite.Open(filepath.Join(t.TempDir(), "mynexus.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	tokens := service.NewTokenService(store.DB(), "mnx_")

	router := gin.New()
	router.GET("/api/v1/chat/sessions", RequireAuth(auth.NewSessionManager(), tokens, "mnx_"), func(c *gin.Context) {
		c.String(http.StatusOK, c.GetString("user_id"))
	})

	req := httptest.NewRequest(http.MethodGet, "/api/v1/chat/sessions", nil)
	req.Header.Set("Authorization", "Bearer integration-secret")
	req.Header.Set("X-MyBooks-User-ID", "42")
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, req)
	if recorder.Code != http.StatusOK || recorder.Body.String() != "mybooks:42" {
		t.Fatalf("response = %d %q, want 200 mybooks:42", recorder.Code, recorder.Body.String())
	}
}

func TestRequireAuthRejectsInvalidOrUntrustedMyBooksUserHeader(t *testing.T) {
	gin.SetMode(gin.TestMode)
	t.Setenv("MYNEXUS_API_TOKEN", "integration-secret")

	store, err := sqlite.Open(filepath.Join(t.TempDir(), "mynexus.db"))
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	tokens := service.NewTokenService(store.DB(), "mnx_")
	apiToken, _, err := tokens.Create("admin", "test")
	if err != nil {
		t.Fatal(err)
	}

	router := gin.New()
	router.GET("/api/v1/chat/sessions", RequireAuth(auth.NewSessionManager(), tokens, "mnx_"), func(c *gin.Context) {
		c.String(http.StatusOK, c.GetString("user_id"))
	})

	tests := []struct {
		name       string
		token      string
		userID     string
		statusCode int
	}{
		{name: "invalid external ID", token: "integration-secret", userID: "0", statusCode: http.StatusBadRequest},
		{name: "per-user token", token: apiToken, userID: "42", statusCode: http.StatusForbidden},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/api/v1/chat/sessions", nil)
			req.Header.Set("Authorization", "Bearer "+test.token)
			req.Header.Set("X-MyBooks-User-ID", test.userID)
			recorder := httptest.NewRecorder()
			router.ServeHTTP(recorder, req)
			if recorder.Code != test.statusCode {
				t.Fatalf("status = %d, want %d: %s", recorder.Code, test.statusCode, recorder.Body.String())
			}
		})
	}
}
