package contract

import (
	"encoding/json"
	"testing"
)

func TestRequiredObjectRefusalOrder(t *testing.T) {
	for _, tc := range []struct{ name, raw, code string }{
		{"valid", `{"id":"native","version":"1","digest":"sha256:x"}`, ""},
		{"malformed", `[`, "malformed"},
		{"null object", `null`, "malformed"},
		{"missing", `{"id":"native","version":"1"}`, "missing"},
		{"missing before null", `{"id":null}`, "missing"},
		{"required null", `{"id":null,"version":"1","digest":"sha256:x"}`, "malformed"},
		{"other null", `{"id":"native","version":"1","digest":"sha256:x","extra":null}`, "malformed"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			fields, code := RequiredObject([]byte(tc.raw), "id version digest")
			if code != tc.code {
				t.Fatalf("code = %q, want %q", code, tc.code)
			}
			if code == "" && string(fields["id"]) != `"native"` {
				t.Fatalf("lost object fields: %v", fields)
			}
		})
	}
}

func TestSharedIdentityPredicates(t *testing.T) {
	digest := "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	if !EvidenceImplementation("native", "1", digest) {
		t.Fatal("valid identity refused")
	}
	for _, token := range []string{"", "sk-secret", "github_pat_secret", "example.com", "127.0.0.1"} {
		if EvidenceImplementation(token, "1", digest) || EvidenceImplementation("native", token, digest) {
			t.Errorf("private/invalid token accepted: %q", token)
		}
	}
	if !IsJSONNull(json.RawMessage(" \nnull\t")) || IsJSONNull(json.RawMessage(`"null"`)) {
		t.Fatal("JSON null semantics changed")
	}
}
