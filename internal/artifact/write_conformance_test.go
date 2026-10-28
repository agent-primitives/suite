package artifact

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type sharedWriteCase struct {
	Name           string `json:"name"`
	Path           string `json:"path"`
	RootDigest     string `json:"rootDigest"`
	ArtifactDigest string `json:"artifactDigest"`
}

func sharedWriteCases(t *testing.T) []sharedWriteCase {
	t.Helper()
	var corpus struct {
		Cases []sharedWriteCase `json:"cases"`
	}
	readStrictJSON(t, "../../testdata/conformance/write-cases.json", &corpus)
	names := map[string]bool{}
	for _, row := range corpus.Cases {
		large := row.Name == "large-instructions" && row.Path == "literal:instructions-above-4mib"
		if names[row.Name] || (!large && row.Path != "testdata/"+row.Name) || !IsValidDigest(row.RootDigest) || !IsValidDigest(row.ArtifactDigest) {
			t.Fatalf("incomplete/duplicate write identity case: %+v", row)
		}
		names[row.Name] = true
	}
	for _, name := range []string{"minimal", "coordinator-workers", "policy-binding", "rich-evaluations", "large-instructions"} {
		if !names[name] {
			t.Fatalf("missing write identity case %q", name)
		}
	}
	if len(corpus.Cases) != 5 {
		t.Fatalf("truncated write identity corpus: %d", len(corpus.Cases))
	}
	return corpus.Cases
}

// These are the same source and output-identity rows used by the Python writer.
// This job independently checks each source's ordinary graph and canonical root.
func TestSharedWriteIdentityCases(t *testing.T) {
	for _, row := range sharedWriteCases(t) {
		t.Run(row.Name, func(t *testing.T) {
			path := filepath.Join("../..", filepath.FromSlash(row.Path))
			if row.Name == "large-instructions" {
				var literals struct {
					Cases []sharedLiteralCase `json:"cases"`
				}
				readStrictJSON(t, "../../testdata/conformance/literal-cases.json", &literals)
				found := false
				for _, literal := range literals.Cases {
					if literal.Name == "instructions-above-4mib" {
						path = literal.fullValidatePath(t)
						found = true
					}
				}
				if !found {
					t.Fatal("missing shared large-literal source")
				}
			} else {
				// Checkouts need not belong to the Windows runner identity.
				path = copyAgentSuiteDirectory(t, path)
				secureDirectoryFixture(t, path)
			}
			content, err := loadPathContent(path)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := validateContent(content); err != nil {
				t.Fatal(err)
			}
			got, err := canonicalDigest(content.entries["agentsuite.json"].Data)
			if err != nil || got != row.RootDigest {
				t.Fatalf("source root identity=%q, err=%v; want %q", got, err, row.RootDigest)
			}
		})
	}
}

type pythonWriterOutput struct {
	Path           string `json:"path"`
	RootDigest     string `json:"rootDigest"`
	ArtifactDigest string `json:"artifactDigest"`
	Valid          bool   `json:"valid"`
	Error          string `json:"error,omitempty"`
}

// A test-only compiled oracle validates actual Python output, not a second
// writer's reconstruction. No Go process or library is used by the runtime SDK.
func TestPythonWriterOutput(t *testing.T) {
	path := os.Getenv("AGENTSUITE_WRITE_ORACLE")
	if path == "" {
		return
	}
	var rows []pythonWriterOutput
	readStrictJSON(t, path, &rows)
	if len(rows) == 0 {
		t.Fatal("empty writer output selection")
	}
	for i, row := range rows {
		content, err := loadPathContent(row.Path)
		if err == nil {
			_, err = validateContent(content)
		}
		if (err == nil) != row.Valid {
			t.Fatalf("output %d (%s): valid=%t, want %t: %v", i, row.Path, err == nil, row.Valid, err)
		}
		if !row.Valid {
			if row.Error == "" || !strings.Contains(err.Error(), row.Error) {
				t.Fatalf("output %d refusal=%v; want %q", i, err, row.Error)
			}
			continue
		}
		if !IsValidDigest(row.RootDigest) {
			t.Fatalf("output %d has no expected root identity", i)
		}
		got, err := canonicalDigest(content.entries["agentsuite.json"].Data)
		if err != nil || got != row.RootDigest {
			t.Fatalf("output %d root=%q, want %q: %v", i, got, row.RootDigest, err)
		}
		if content.artifactDigest != row.ArtifactDigest {
			t.Fatalf("output %d exact OCI digest=%q, want %q", i, content.artifactDigest, row.ArtifactDigest)
		}
	}
}
