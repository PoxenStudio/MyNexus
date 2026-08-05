package auth

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
)

// GenerateAPIToken creates a new random token string with the given prefix
// (e.g. "mnx_") plus its SHA-256 hash for storage. Only the hash is ever
// persisted — see docs/系统设计文档.md §8.2.
func GenerateAPIToken(prefix string) (raw string, hash string, err error) {
	buf := make([]byte, 24)
	if _, err := rand.Read(buf); err != nil {
		return "", "", fmt.Errorf("generate token bytes: %w", err)
	}
	raw = prefix + hex.EncodeToString(buf)
	return raw, HashToken(raw), nil
}

func HashToken(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}
