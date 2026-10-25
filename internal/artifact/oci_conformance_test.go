package artifact

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"
	"testing"
)

type ociCase struct {
	Name           string             `json:"name"`
	Layout         string             `json:"layout"`
	Files          map[string]*[]byte `json:"files,omitempty"`
	Valid          *bool              `json:"valid"`
	ArchiveCase    string             `json:"archiveCase,omitempty"`
	ArtifactDigest string             `json:"artifactDigest,omitempty"`
	Entries        []contentEntry     `json:"entries,omitempty"`
	Error          string             `json:"error,omitempty"`
}

func ociResult(t *testing.T, c ociCase) ociCase {
	t.Helper()
	root := t.TempDir()
	if c.Layout != "" {
		if filepath.Base(c.Layout) != c.Layout {
			t.Fatal("invalid fixture layout")
		}
		source := filepath.Join("../../testdata/conformance/oci", c.Layout)
		err := filepath.WalkDir(source, func(path string, d os.DirEntry, err error) error {
			if err != nil {
				return err
			}
			rel, err := filepath.Rel(source, path)
			if err != nil {
				return err
			}
			if d.IsDir() {
				return os.MkdirAll(filepath.Join(root, rel), 0o755)
			}
			raw, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			return os.WriteFile(filepath.Join(root, rel), raw, 0o644)
		})
		if err != nil {
			t.Fatal(err)
		}
	}
	for path, data := range c.Files {
		if !filepath.IsLocal(path) || strings.Contains(path, "\\") {
			t.Fatal("invalid fixture path")
		}
		name := filepath.Join(root, filepath.FromSlash(path))
		if data == nil {
			if err := os.Remove(name); err != nil {
				t.Fatal(err)
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(name), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(name, *data, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	content, err := loadOCILayoutContent(root)
	valid := err == nil
	c.Valid, c.Entries, c.ArtifactDigest, c.Error = &valid, nil, "", ""
	if err != nil {
		c.Error = err.Error()
		return c
	}
	if content.sourceType != "oci-layout" {
		t.Fatal("missing OCI source")
	}
	c.ArtifactDigest = content.artifactDigest
	c.Entries = []contentEntry{}
	for _, entry := range content.entries {
		c.Entries = append(c.Entries, entry)
	}
	sort.Slice(c.Entries, func(i, j int) bool { return c.Entries[i].Path < c.Entries[j].Path })
	return c
}

func TestSharedOCICases(t *testing.T) {
	// Test-only actual-Go differential oracle, never a runtime SDK dependency.
	if input := os.Getenv("AGENTSUITE_OCI_ORACLE"); input != "" {
		raw, err := os.ReadFile(input)
		if err != nil {
			t.Fatal(err)
		}
		var cases []ociCase
		if err := json.Unmarshal(raw, &cases); err != nil {
			t.Fatal(err)
		}
		for i, c := range cases {
			cases[i] = ociResult(t, c)
		}
		raw, err = json.Marshal(cases)
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(input+".result", raw, 0o600); err != nil {
			t.Fatal(err)
		}
		return
	}
	var corpus struct {
		Cases []ociCase `json:"cases"`
	}
	var raw json.RawMessage
	readStrictJSON(t, "../../testdata/conformance/oci-cases.json", &raw)
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&corpus); err != nil {
		t.Fatal(err)
	}
	var archive struct {
		Cases []archiveCase `json:"cases"`
	}
	data, err := os.ReadFile("../../testdata/conformance/archive-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(data, &archive); err != nil {
		t.Fatal(err)
	}
	goldens := map[string][]contentEntry{}
	for _, c := range archive.Cases {
		if c.Valid != nil && *c.Valid {
			goldens[c.Name] = c.Entries
		}
	}
	names := map[string]bool{}
	positives, negatives := 0, 0
	for _, c := range corpus.Cases {
		requireDirectoryCaseName(t, names, "oci", c.Name)
		if c.Valid == nil {
			t.Fatal("missing OCI validity")
		}
		if *c.Valid {
			positives++
		} else {
			negatives++
		}
		t.Run(c.Name, func(t *testing.T) {
			got := ociResult(t, c)
			if *got.Valid != *c.Valid {
				t.Fatalf("valid=%t error=%s; want %t", *got.Valid, got.Error, *c.Valid)
			}
			if *c.Valid {
				entries, ok := goldens[c.ArchiveCase]
				if !ok || c.ArtifactDigest == "" || got.ArtifactDigest != c.ArtifactDigest || !reflect.DeepEqual(got.Entries, entries) {
					t.Fatalf("identity/content mismatch: digest=%s entries=%+v", got.ArtifactDigest, got.Entries)
				}
			}
		})
	}
	if positives < 29 || negatives < 83 {
		t.Fatal("truncated OCI acceptance/refusal corpus")
	}
}
