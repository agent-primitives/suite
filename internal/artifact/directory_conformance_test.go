package artifact

import (
	"encoding/hex"
	"testing"
)

func requireDirectoryCaseName(t *testing.T, names map[string]bool, group, name string) {
	t.Helper()
	key := group + "/" + name
	if name == "" || names[key] {
		t.Fatalf("missing or duplicate %s case name: %q", group, name)
	}
	names[key] = true
}

func TestSharedDirectoryRules(t *testing.T) {
	var corpus struct {
		Limits struct {
			Entries       int   `json:"entries"`
			ContentBytes  int64 `json:"contentBytes"`
			RetainedBytes int64 `json:"retainedBytes"`
			JSONBytes     int64 `json:"jsonBytes"`
			PathBytes     int   `json:"pathBytes"`
		} `json:"limits"`
		Paths []struct {
			Name  string `json:"name"`
			Value string `json:"value"`
			Hex   string `json:"hex"`
			Valid bool   `json:"valid"`
		} `json:"paths"`
		Links []struct {
			Name   string `json:"name"`
			Path   string `json:"path"`
			Target string `json:"target"`
			Valid  bool   `json:"valid"`
		} `json:"links"`
		Collisions []struct {
			Name    string `json:"name"`
			First   string `json:"first"`
			Second  string `json:"second"`
			Collide bool   `json:"collide"`
		} `json:"collisions"`
		Retention []struct {
			Name     string `json:"name"`
			Path     string `json:"path"`
			Size     int64  `json:"size"`
			Retained bool   `json:"retained"`
		} `json:"retention"`
		Budgets []struct {
			Name    string `json:"name"`
			Current int64  `json:"current"`
			Size    int64  `json:"size"`
			Valid   bool   `json:"valid"`
		} `json:"budgets"`
	}
	readStrictJSON(t, "../../testdata/conformance/directory-cases.json", &corpus)
	for name, population := range map[string][2]int{
		"paths": {len(corpus.Paths), 15}, "links": {len(corpus.Links), 9},
		"collisions": {len(corpus.Collisions), 9}, "retention": {len(corpus.Retention), 7},
		"budgets": {len(corpus.Budgets), 5},
	} {
		if population[0] < population[1] {
			t.Fatalf("truncated %s corpus: %d cases", name, population[0])
		}
	}
	names := map[string]bool{}
	if corpus.Limits.Entries != maxContentEntries || corpus.Limits.ContentBytes != maxContentBytes || corpus.Limits.RetainedBytes != maxRetainedMetadataBytes || corpus.Limits.JSONBytes != maxJSONBytes || corpus.Limits.PathBytes != maxPathBytes {
		t.Fatal("directory corpus limits disagree with implementation")
	}
	for _, c := range corpus.Paths {
		requireDirectoryCaseName(t, names, "paths", c.Name)
		t.Run("path/"+c.Name, func(t *testing.T) {
			value := c.Value
			if c.Hex != "" {
				raw, err := hex.DecodeString(c.Hex)
				if err != nil {
					t.Fatal(err)
				}
				value = string(raw)
			}
			if _, err := validateContentPath(value); (err == nil) != c.Valid {
				t.Fatalf("path error=%v, want valid=%t", err, c.Valid)
			}
		})
	}
	for _, c := range corpus.Links {
		requireDirectoryCaseName(t, names, "links", c.Name)
		t.Run("link/"+c.Name, func(t *testing.T) {
			if err := validateLinkTarget(c.Path, c.Target); (err == nil) != c.Valid {
				t.Fatalf("link error=%v, want valid=%t", err, c.Valid)
			}
		})
	}
	for _, c := range corpus.Collisions {
		requireDirectoryCaseName(t, names, "collisions", c.Name)
		t.Run("collision/"+c.Name, func(t *testing.T) {
			content := &contentSet{entries: map[string]contentEntry{}, folded: map[string]string{}}
			if err := content.add(contentEntry{Path: c.First}); err != nil {
				t.Fatal(err)
			}
			if err := content.add(contentEntry{Path: c.Second}); (err != nil) != c.Collide {
				t.Fatalf("collision error=%v, want collision=%t", err, c.Collide)
			}
		})
	}
	for _, c := range corpus.Retention {
		requireDirectoryCaseName(t, names, "retention", c.Name)
		t.Run("retention/"+c.Name, func(t *testing.T) {
			if got := shouldRetainMetadata(c.Path, c.Size); got != c.Retained {
				t.Fatalf("retained=%t, want %t", got, c.Retained)
			}
		})
	}
	for _, c := range corpus.Budgets {
		requireDirectoryCaseName(t, names, "budgets", c.Name)
		t.Run("budget/"+c.Name, func(t *testing.T) {
			got, err := addRetainedMetadata(c.Current, c.Size)
			if (err == nil) != c.Valid || c.Valid && got != c.Current+c.Size {
				t.Fatalf("budget=%d, error=%v, want valid=%t", got, err, c.Valid)
			}
		})
	}
}
