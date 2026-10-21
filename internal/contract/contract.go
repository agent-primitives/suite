// Package contract holds shared checks below portable models and artifact validation.
package contract

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"path"
	"regexp"
	"strings"
	"unicode/utf8"
)

const MaxPathBytes = 1024

var (
	IdentifierPattern      = regexp.MustCompile(`^[a-z0-9][a-z0-9._-]{0,127}$`)
	EnvPattern             = regexp.MustCompile(`^[A-Z_][A-Z0-9_]*$`)
	evidenceTokenPattern   = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`)
	evidencePrivatePattern = regexp.MustCompile(`(?i)^(sk[-_]|gh[pousr]_|github_pat_|AKIA|ASIA|eyJ)|^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$`)
	evidenceIPPattern      = regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$`)
)

func ValidateContentPath(value string) (string, error) {
	if value == "" || len(value) > MaxPathBytes || !utf8.ValidString(value) || strings.ContainsRune(value, '\x00') {
		return "", fmt.Errorf("unsafe content path %q", value)
	}
	if strings.Contains(value, "\\") || strings.HasPrefix(value, "/") {
		return "", fmt.Errorf("content path must be relative POSIX syntax: %q", value)
	}
	clean := path.Clean(value)
	if clean != value || clean == "." || clean == ".." || strings.HasPrefix(clean, "../") {
		return "", fmt.Errorf("content path is not normalized below the root: %q", value)
	}
	for _, part := range strings.Split(clean, "/") {
		if part == "" || part == "." || part == ".." {
			return "", fmt.Errorf("content path contains an unsafe segment: %q", value)
		}
	}
	return clean, nil
}

func UnsafeInjectionEnv(name string) bool {
	return strings.HasPrefix(name, "LD_") || name == "PYTHONPATH" || name == "NODE_OPTIONS" || name == "BASH_ENV"
}

func EvidenceToken(value string) bool {
	return evidenceTokenPattern.MatchString(value) && !evidencePrivatePattern.MatchString(value) && !evidenceIPPattern.MatchString(value)
}

func IsValidDigest(value string) bool {
	if !strings.HasPrefix(value, "sha256:") || len(value) != len("sha256:")+64 {
		return false
	}
	for _, r := range value[len("sha256:"):] {
		if r < '0' || r > '9' && r < 'a' || r > 'f' {
			return false
		}
	}
	return true
}

func DigestBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func IsJSONNull(raw json.RawMessage) bool {
	return bytes.Equal(bytes.TrimSpace(raw), []byte("null"))
}

// EvidenceImplementation checks the same public implementation identity used by
// runtime profiles and evaluation evidence without depending on either model.
func EvidenceImplementation(id, version, digest string) bool {
	return EvidenceToken(id) && EvidenceToken(version) && IsValidDigest(digest)
}

// RequiredObject preserves missing-before-null refusal ordering. Every present
// field, not only required ones, must be non-null. Codes are interpreted by the
// caller so model errors and sanitized evidence refusals keep their own types.
func RequiredObject(data []byte, required string) (map[string]json.RawMessage, string) {
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil || fields == nil {
		return nil, "malformed"
	}
	for _, key := range strings.Fields(required) {
		if _, ok := fields[key]; !ok {
			return nil, "missing"
		}
	}
	for _, value := range fields {
		if IsJSONNull(value) {
			return nil, "malformed"
		}
	}
	return fields, ""
}
