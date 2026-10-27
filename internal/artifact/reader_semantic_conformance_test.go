package artifact

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

// Frozen original Go evaluation/policy table mutations and current ordinary
// semantic boundary probes. Every row is a full package, not an isolated record.
func sharedReaderSemanticCases(t *testing.T) []sharedGraphCase {
	t.Helper()
	raw, err := os.ReadFile("../../testdata/conformance/reader-semantic-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var corpus sharedGraphCases
	if err := decodeStrict(raw, &corpus); err != nil {
		t.Fatal(err)
	}
	top := sharedGraphFields(t, raw, "cases")
	var rows []json.RawMessage
	if err := json.Unmarshal(top["cases"], &rows); err != nil {
		t.Fatal(err)
	}
	names := map[string]bool{}
	valid := 0
	for i, row := range corpus.Cases {
		fields := sharedGraphFields(t, rows[i], "name", "origin", "sourceType", "valid", "phase", "refusal", "fullPath", "entries")
		for key, value := range fields {
			if bytes.Equal(value, []byte("null")) {
				t.Fatalf("%s: field %s must not be null", row.Name, key)
			}
		}
		var entries []json.RawMessage
		if err := json.Unmarshal(fields["entries"], &entries); err != nil {
			t.Fatal(err)
		}
		for j, entry := range entries {
			fields := sharedGraphFields(t, entry, "path", "type", "mode", "uid", "gid", "size", "digest", "linkTarget", "bytes")
			for key, value := range fields {
				if key != "bytes" && bytes.Equal(value, []byte("null")) {
					t.Fatalf("%s: entry field %s must not be null", row.Name, key)
				}
			}
			e := row.Entries[j]
			wantMode := uint32(0o644)
			if e.Type == "directory" {
				wantMode = 0o755
			}
			if e.Mode != wantMode || e.UID != 0 || e.GID != 0 || e.LinkTarget != "" {
				t.Fatalf("%s: nonportable fixture metadata at %s", row.Name, e.Path)
			}
		}
		if row.Name == "" || names[row.Name] || row.Valid == nil || row.FullPath == nil ||
			!*row.FullPath || row.SourceType != "directory" || len(row.Entries) == 0 ||
			!strings.HasPrefix(row.Origin, "d753475d3313507bb3297d06b28ec373287e3791:") {
			t.Fatalf("incomplete, duplicate or non-full-directory case %q", row.Name)
		}
		names[row.Name] = true
		if *row.Valid {
			valid++
			if row.Phase != "" || row.Refusal != "" {
				t.Fatalf("%s: accepted row has a refusal", row.Name)
			}
		} else if row.Phase != "ValidatePath" || row.Refusal == "" || strings.Contains(row.Refusal, "\n") {
			t.Fatalf("%s: refused row must freeze its first complete diagnostic", row.Name)
		}
	}
	required := []string{
		"eval-graph-empty-cases",
		"eval-graph-too-many-cases",
		"eval-graph-invalid-count-limit",
		"eval-graph-invalid-size-limit",
		"eval-graph-case-too-large",
		"eval-graph-duplicate-reference",
		"eval-graph-case-digest",
		"eval-graph-cross-agent-path",
		"eval-graph-duplicate-ids",
		"eval-graph-missing-case",
		"eval-graph-orphan-agent",
		"eval-graph-embedded-result",
		"eval-binding-null",
		"eval-binding-wrong-path",
		"eval-binding-bad-index-digest",
		"eval-binding-multiple-indexes",
		"eval-binding-unbound-tree",
		"eval-assertion-contains",
		"eval-assertion-notContains",
		"eval-assertion-regex",
		"eval-assertion-toolCalled",
		"eval-assertion-toolNotCalled",
		"eval-assertion-judge",
		"eval-assertion-extension",
		"eval-assertion-known-non-critical",
		"eval-assertion-unknown-critical",
		"eval-assertion-unknown-implicit-critical",
		"eval-assertion-unknown-property",
		"eval-assertion-irrelevant-empty-field",
		"eval-assertion-null-critical",
		"eval-assertion-blank-value",
		"eval-assertion-control-value",
		"eval-assertion-line-separator-value",
		"eval-assertion-paragraph-separator-value",
		"eval-assertion-line-separator-tool",
		"eval-assertion-paragraph-separator-tool",
		"eval-assertion-missing-id",
		"eval-assertion-missing-value",
		"eval-assertion-missing-judge-version",
		"eval-assertion-bad-judge-score",
		"eval-assertion-non-ASCII-judge-identity",
		"eval-runs-default-single-run",
		"eval-runs-all-runs-must-pass",
		"eval-runs-minimum-passes",
		"eval-runs-one-run-one-pass",
		"eval-runs-zero-runs",
		"eval-runs-null-runs",
		"eval-runs-zero-min-passes",
		"eval-runs-null-min-passes",
		"eval-strict-invalid-regex",
		"eval-strict-duplicate-JSON-keys",
		"eval-strict-unknown-field",
		"eval-strict-empty-input",
		"policy-ref-null",
		"policy-ref-array",
		"policy-ref-missing-path",
		"policy-ref-null-path",
		"policy-ref-unknown-ref-field",
		"policy-ref-missing-descriptor",
		"policy-ref-null-descriptor",
		"policy-ref-missing-digest",
		"policy-ref-missing-size",
		"policy-ref-missing-media",
		"policy-ref-null-digest",
		"policy-ref-null-size",
		"policy-ref-null-media",
		"policy-ref-unknown-descriptor-field",
		"policy-ref-negative-size",
		"policy-ref-wrong-size",
		"policy-ref-invalid-digest",
		"policy-ref-wrong-digest",
		"policy-ref-wrong-media",
		"policy-ref-version-mismatch",
		"policy-document-v2-wrong-version-media",
		"policy-document-noncanonical-raw-descriptor",
		"policy-document-not-JSON",
		"policy-before-decode-invalid-digest",
		"policy-before-decode-negative-size",
		"policy-before-decode-wrong-media",
		"policy-before-decode-wrong-hash",
		"policy-before-decode-wrong-size",
		"policy-unowned-missing",
		"policy-unowned-cross-agent",
		"policy-unowned-outside-namespace",
		"policy-unowned-orphan-file",
		"policy-unowned-nested-file",
		"policy-unowned-stale-policy-bytes",
		"policy-unowned-noncanonical-canonical-descriptor",
		"eval-default-suite",
		"eval-source-index-version",
		"eval-source-index-media",
		"eval-source-index-ref-media",
		"eval-source-index-ref-size",
		"eval-source-case-version",
		"eval-source-case-media",
		"eval-source-case-ref-media",
		"eval-source-case-ref-size",
		"eval-source-case-invalid-digest",
		"eval-source-case-empty-assertions",
		"eval-source-case-null-value",
		"eval-source-rubric-control",
		"policy-count-v1-4096",
		"policy-count-v1-4097",
		"policy-count-v2-4096",
		"policy-count-v2-4097",
		"policy-empty-namespace",
		"policy-unbound-file",
		"policy-effective-digest",
		"policy-stale-ancestor",
		"policy-repinned-ancestor",
		"eval-stale-order",
		"eval-repinned-order",
	}
	if len(corpus.Cases) != len(required) || valid != 18 {
		t.Fatalf("reader populations = %d cases, %d accepted; want 112/18", len(corpus.Cases), valid)
	}
	for _, name := range required {
		if !names[name] {
			t.Fatalf("required reader case %q missing", name)
		}
	}
	return corpus.Cases
}

// Namespace-only failures have no stable first diagnostic: their entire list
// comes from a map. Select its lexical first complete diagnostic; semantic
// failures retain the owning-agent diagnostic ahead of that unordered tail.
func semanticReaderRefusal(err error) string {
	lines := strings.Split(err.Error(), "\n")
	if strings.HasPrefix(lines[0], "eval path ") || strings.HasPrefix(lines[0], "policy path ") {
		sort.Strings(lines)
	}
	return lines[0]
}

func TestSharedReaderSemanticCases(t *testing.T) {
	for _, row := range sharedReaderSemanticCases(t) {
		t.Run(row.Name, func(t *testing.T) {
			// content verifies sorted entries and literal size/digest, including
			// files whose production Data retention is intentionally absent.
			_, err := validateContent(row.content(t))
			refusal := ""
			if err != nil {
				// Other unvisited files may produce additional map-ordered
				// namespace diagnostics. Freeze the intended first refusal only.
				refusal = semanticReaderRefusal(err)
			}
			if (err == nil) != *row.Valid || refusal != row.Refusal {
				t.Fatalf("ordinary validator error = %v; want valid=%t, refusal=%q", err, *row.Valid, row.Refusal)
			}
			row.fullValidatePath(t)
		})
	}
}

// Also replay every accepted snapshot through OCI. Author portable modes rather
// than copying Windows host permissions into the archive.
func TestSharedReaderSemanticOCIPositives(t *testing.T) {
	count := 0
	for _, row := range sharedReaderSemanticCases(t) {
		if !*row.Valid {
			continue
		}
		count++
		t.Run(row.Name, func(t *testing.T) {
			root := t.TempDir()
			content := row.content(t)
			for _, e := range row.Entries {
				if e.Type == "directory" {
					if err := os.MkdirAll(filepath.Join(root, filepath.FromSlash(e.Path)), 0o755); err != nil {
						t.Fatal(err)
					}
				} else {
					// content already validates and decodes the same frozen bytes.
					mustWrite(t, root, e.Path, content.entries[e.Path].Data)
				}
			}
			source := writeTestOCILayoutTar(t, literalPortableTar(t, root))
			if _, err := ValidatePath(source); err != nil {
				t.Fatal(err)
			}
		})
	}
	if count != 18 {
		t.Fatalf("OCI accepted population = %d; want 18", count)
	}
}
