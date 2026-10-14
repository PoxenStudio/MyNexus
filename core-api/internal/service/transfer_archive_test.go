package service

import (
	"strings"
	"testing"
	"unicode/utf8"
)

func TestSanitizeExportFilenameLimitsCompleteNameTo100Runes(t *testing.T) {
	filename := sanitizeExportFilename(strings.Repeat("书", 150), "12345678-1234-1234-1234-123456789abc")

	if got := utf8.RuneCountInString(filename); got > 100 {
		t.Fatalf("filename has %d Unicode characters; want at most 100", got)
	}
	if got := len([]byte(filename)); got > 255 {
		t.Fatalf("filename has %d bytes; want at most 255", got)
	}
	if !strings.HasSuffix(filename, ".zip") {
		t.Fatalf("filename %q does not end with .zip", filename)
	}
}

func TestSanitizeExportFilenameRemovesUnsafeCharacters(t *testing.T) {
	filename := sanitizeExportFilename(` /a:b*?"<>|\\ book. `, "12345678-1234-1234-1234-123456789abc")

	if strings.ContainsAny(filename, `/\:*?"<>|`) {
		t.Fatalf("filename contains unsafe characters: %q", filename)
	}
	if !strings.HasSuffix(filename, "-12345678.zip") {
		t.Fatalf("filename %q is missing its task-specific suffix", filename)
	}
}
