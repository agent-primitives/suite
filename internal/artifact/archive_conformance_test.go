package artifact

import (
	"bytes"
	"encoding/json"
	"os"
	"reflect"
	"sort"
	"testing"
)

type archiveCase struct {
	Name    string         `json:"name"`
	Gzip    []byte         `json:"gzip"`
	Valid   *bool          `json:"valid"`
	Entries []contentEntry `json:"entries"`
	Error   string         `json:"error,omitempty"`
}

func archiveResult(c archiveCase) archiveCase {
	content, err := loadContentLayer(bytes.NewReader(c.Gzip))
	valid := err == nil
	c.Valid = &valid
	c.Entries = nil
	if err != nil {
		c.Error = err.Error()
		return c
	}
	c.Entries = []contentEntry{}
	for _, entry := range content.entries {
		c.Entries = append(c.Entries, entry)
	}
	sort.Slice(c.Entries, func(i, j int) bool { return c.Entries[i].Path < c.Entries[j].Path })
	return c
}

func TestSharedArchiveCases(t *testing.T) {
	// Test-only differential mode uses exactly this private reference loader.
	// Paths are supplied by the local test harness, never a product API.
	if input := os.Getenv("AGENTSUITE_ARCHIVE_ORACLE"); input != "" {
		raw, err := os.ReadFile(input)
		if err != nil {
			t.Fatal(err)
		}
		var cases []archiveCase
		if err := json.Unmarshal(raw, &cases); err != nil {
			t.Fatal(err)
		}
		for i, c := range cases {
			cases[i] = archiveResult(c)
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
		Cases []archiveCase `json:"cases"`
	}
	// The typed format codec treats slices as JSON arrays. Fixture bytes use
	// encoding/json's base64 convention, after the same strict JSON checks.
	var raw json.RawMessage
	readStrictJSON(t, "../../testdata/conformance/archive-cases.json", &raw)
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&corpus); err != nil {
		t.Fatal(err)
	}
	if len(corpus.Cases) < 94 {
		t.Fatal("truncated archive corpus")
	}
	names := map[string]bool{}
	positives, negatives := 0, 0
	for _, c := range corpus.Cases {
		requireDirectoryCaseName(t, names, "archive", c.Name)
		if c.Valid == nil {
			t.Fatal("missing archive validity")
		}
		if *c.Valid {
			positives++
		} else {
			negatives++
		}
		t.Run(c.Name, func(t *testing.T) {
			got := archiveResult(c)
			if *got.Valid != *c.Valid || *c.Valid && !reflect.DeepEqual(got.Entries, c.Entries) {
				t.Fatalf("valid=%t error=%s entries=%+v; want valid=%t entries=%+v", *got.Valid, got.Error, got.Entries, *c.Valid, c.Entries)
			}
		})
	}
	if positives < 40 || negatives < 54 {
		t.Fatal("truncated archive acceptance/refusal populations")
	}
}
