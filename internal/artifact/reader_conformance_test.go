package artifact

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Reader rows use the existing complete graph transport, but exercise the
// ordinary validator including policy/evaluation semantics, not a graph subset.
func sharedReaderCases(t *testing.T) []sharedGraphCase {
	t.Helper()
	raw, err := os.ReadFile("../../testdata/conformance/reader-cases.json")
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
		"reader-minimal", "reader-rich",
		"policy-v1-root-path", "policy-v1-empty-paths", "policy-v1-unclean-path", "policy-v1-capabilities",
		"policy-v2-empty-allowlist", "policy-v2-ipv4", "policy-v2-invalid-ipv4", "policy-orphan-subdirectory",
		"eval-orphan-file", "eval-agent-mismatch", "eval-input-c0", "eval-input-vt",
		"eval-input-next-line", "eval-input-nbsp", "eval-input-bom", "eval-unknown-value-c0",
		"eval-rubric-byte-limit", "eval-pattern-byte-limit", "eval-regex-lookahead",
		"eval-minpasses-without-runs", "eval-minpasses-exceeds-runs", "eval-duplicate-assertion-ids",
		"eval-case-filename", "eval-raw-minscore-fraction", "eval-raw-runs-exponent",
		"agent-id-newline", "eval-id-newline", "eval-judge-newline",
	}
	if len(corpus.Cases) != len(required) || valid != 7 {
		t.Fatalf("reader populations = %d cases, %d accepted; want 30/7", len(corpus.Cases), valid)
	}
	for _, name := range required {
		if !names[name] {
			t.Fatalf("required reader case %q missing", name)
		}
	}
	return corpus.Cases
}

func TestSharedReaderCases(t *testing.T) {
	for _, row := range sharedReaderCases(t) {
		t.Run(row.Name, func(t *testing.T) {
			// content verifies sorted entries and literal size/digest, including
			// files whose production Data retention is intentionally absent.
			_, err := validateContent(row.content(t))
			refusal := ""
			if err != nil {
				// Other unvisited files may produce additional map-ordered
				// namespace diagnostics. Freeze the intended first refusal only.
				refusal = strings.Split(err.Error(), "\n")[0]
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
func TestSharedReaderOCIPositives(t *testing.T) {
	count := 0
	for _, row := range sharedReaderCases(t) {
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
	if count != 7 {
		t.Fatalf("OCI accepted population = %d; want 7", count)
	}
}

// Go's actual bundled schema is the regex-flavor oracle. In particular Go \S
// includes C0 separators, VT, NEL, NBSP and BOM. TrimSpace at the semantic layer
// separately rejects VT/NEL/NBSP-only input. These are not schema changes.
func TestSharedReaderSchemaPatterns(t *testing.T) {
	probes := map[string]struct {
		schema string
		path   string
		valid  bool
	}{
		"reader-rich":           {"eval-case.schema.json", "evals/writer/cases/capital.json", true},
		"eval-input-c0":         {"eval-case.schema.json", "evals/writer/cases/capital.json", true},
		"eval-input-vt":         {"eval-case.schema.json", "evals/writer/cases/capital.json", true},
		"eval-input-next-line":  {"eval-case.schema.json", "evals/writer/cases/capital.json", true},
		"eval-input-nbsp":       {"eval-case.schema.json", "evals/writer/cases/capital.json", true},
		"eval-input-bom":        {"eval-case.schema.json", "evals/writer/cases/capital.json", true},
		"eval-unknown-value-c0": {"eval-case.schema.json", "evals/writer/cases/capital.json", true},
		"agent-id-newline":      {"agent.schema.json", "agents/writer.json", false},
		"eval-id-newline":       {"eval-case.schema.json", "evals/writer/cases/capital.json", false},
		"eval-judge-newline":    {"eval-case.schema.json", "evals/writer/cases/capital.json", false},
	}
	count, accepted := 0, 0
	for _, row := range sharedReaderCases(t) {
		probe, ok := probes[row.Name]
		if !ok {
			continue
		}
		count++
		if probe.valid {
			accepted++
		}
		t.Run(row.Name, func(t *testing.T) {
			data, err := row.content(t).data(probe.path)
			if err != nil {
				t.Fatal(err)
			}
			validateSchemaJSON(t, compileReferenceSchema(t, probe.schema), string(data), probe.valid)
		})
	}
	if count != 10 || accepted != 7 {
		t.Fatalf("schema proof populations = %d selected, %d accepted; want 10/7", count, accepted)
	}
}
