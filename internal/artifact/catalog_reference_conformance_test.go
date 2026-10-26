package artifact

import (
	"bytes"
	"encoding/base64"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestSharedCatalogReferenceCases(t *testing.T) {
	var corpus struct {
		Cases []struct {
			Name    string `json:"name"`
			File    string `json:"file"`
			Schema  string `json:"schema"`
			Bytes   string `json:"bytes"`
			Valid   *bool  `json:"valid"`
			Refusal string `json:"refusal"`
			Pointer string `json:"pointer"`
			Code    string `json:"code"`
		} `json:"cases"`
	}
	readStrictJSON(t, "../../testdata/conformance/catalog-reference-cases.json", &corpus)
	if len(corpus.Cases) != 5 {
		t.Fatal("truncated catalog-reference corpus")
	}
	names := map[string]bool{}
	valid := 0
	for _, c := range corpus.Cases {
		requireDirectoryCaseName(t, names, "catalog-reference", c.Name)
		if c.File != "agentsuite.json" || c.Schema != "suite.schema.json" || c.Valid == nil {
			t.Fatal("missing catalog-reference source/schema/expectation")
		}
		if *c.Valid {
			valid++
		} else if c.Refusal == "" || c.Pointer == "" || c.Code == "" {
			t.Fatal("missing catalog-reference refusal context")
		}
		t.Run(c.Name, func(t *testing.T) {
			raw, err := base64.StdEncoding.DecodeString(c.Bytes)
			if err != nil {
				t.Fatal(err)
			}
			root := writeMinimalSuite(t)
			mustWrite(t, root, c.File, raw)
			stored, err := os.ReadFile(filepath.Join(root, c.File))
			if err != nil || !bytes.Equal(stored, raw) {
				t.Fatalf("fixture changed literal root bytes: %v", err)
			}
			secureDirectoryFixture(t, root)
			// Strict decoding accepts missing/empty/invalid reference IDs.
			// The catalog's semantic loader owns their refusal.
			var suite Suite
			readStrictJSON(t, filepath.Join(root, c.File), &suite)
			content, err := loadDirectory(root)
			if err != nil {
				t.Fatal(err)
			}
			v := validator{suite: suite, content: content}
			check := func(t *testing.T, err error) {
				t.Helper()
				if (err == nil) != *c.Valid {
					t.Fatalf("valid=%t error=%v; want valid=%t", err == nil, err, *c.Valid)
				}
				if !*c.Valid && !strings.Contains(err.Error(), c.Refusal) {
					t.Fatalf("wrong refusal, want %q: %v", c.Refusal, err)
				}
			}
			t.Run("strict-and-loader", func(t *testing.T) {
				check(t, v.loadToolProviders())
			})
			t.Run("full-package", func(t *testing.T) {
				_, err := ValidatePath(root)
				check(t, err)
			})
		})
	}
	if valid != 2 {
		t.Fatal("catalog-reference population changed")
	}
}
