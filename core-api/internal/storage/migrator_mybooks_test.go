package storage

import (
	"database/sql"
	"strings"
	"testing"

	_ "modernc.org/sqlite"
)

func TestCheckMyBooksIDDuplicatesReportsValues(t *testing.T) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	if _, err := db.Exec(`CREATE TABLE books (mybooks_id INTEGER)`); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(`INSERT INTO books (mybooks_id) VALUES (17), (17), (29), (NULL)`); err != nil {
		t.Fatal(err)
	}

	err = checkMyBooksIDDuplicates(db)
	if err == nil || !strings.Contains(err.Error(), "17 (2 books)") {
		t.Fatalf("duplicate check error = %v, want ID 17 and its count", err)
	}
}
