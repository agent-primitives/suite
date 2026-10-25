//go:build unix || windows

package artifact

import (
	"bytes"
	"encoding/hex"
	"os"
	"path/filepath"
	"testing"
)

type directoryAccessCase struct {
	Name      string `json:"name"`
	Platform  string `json:"platform"`
	Kind      string `json:"kind"`
	Path      string `json:"path"`
	Target    string `json:"target"`
	Mode      uint32 `json:"mode"`
	DACL      string `json:"dacl"`
	Protected bool   `json:"protected"`
	Valid     bool   `json:"valid"`
}

func TestSharedDirectoryAccess(t *testing.T) {
	var corpus struct {
		Files []struct {
			Path string `json:"path"`
			Hex  string `json:"hex"`
		} `json:"files"`
		Cases []directoryAccessCase `json:"cases"`
	}
	readStrictJSON(t, "../../testdata/conformance/directory-access-cases.json", &corpus)
	if len(corpus.Files) < 3 || len(corpus.Cases) < 20 {
		t.Fatal("truncated directory access corpus")
	}
	names := map[string]bool{}
	for _, file := range corpus.Files {
		requireDirectoryCaseName(t, names, "files", file.Path)
	}
	count := 0
	for _, c := range corpus.Cases {
		requireDirectoryCaseName(t, names, "cases", c.Name)
		if c.Platform != "all" && c.Platform != "posix" && c.Platform != "windows" {
			t.Fatalf("unknown directory platform: %q", c.Platform)
		}
		if c.Platform != "all" && c.Platform != directoryCasePlatform {
			continue
		}
		count++
		t.Run(c.Name, func(t *testing.T) {
			root := t.TempDir()
			// Fixture setup, before any intentionally unsafe case mutation.
			if err := os.Chmod(root, 0700); err != nil {
				t.Fatal(err)
			}
			for _, file := range corpus.Files {
				data, err := hex.DecodeString(file.Hex)
				if err != nil {
					t.Fatal(err)
				}
				name := filepath.Join(root, filepath.FromSlash(file.Path))
				if err := os.MkdirAll(filepath.Dir(name), 0700); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(name, data, 0600); err != nil {
					t.Fatal(err)
				}
			}
			secureDirectoryFixture(t, root)
			input := root
			if c.Kind == "root-alias" {
				input = filepath.Join(t.TempDir(), "alias")
				directoryFixtureAlias(t, input, root)
			} else if c.Kind != "none" {
				directoryFixtureMutation(t, root, c)
			}
			content, err := loadDirectory(input)
			if (err == nil) != c.Valid {
				t.Fatalf("directory error=%v, want valid=%t", err, c.Valid)
			}
			if !c.Valid {
				return
			}
			for _, file := range corpus.Files {
				data, err := hex.DecodeString(file.Hex)
				if err != nil {
					t.Fatal(err)
				}
				entry, ok := content.entries[file.Path]
				if !ok || entry.Type != "file" || entry.Mode != 0644 || entry.Size != int64(len(data)) || entry.Digest != digestBytes(data) || entry.UID != 0 || entry.GID != 0 {
					t.Fatalf("unexpected raw entry: %+v", entry)
				}
				if shouldRetainMetadata(file.Path, int64(len(data))) {
					if entry.Data == nil || !bytes.Equal(entry.Data, data) {
						t.Fatalf("retained bytes differ: %s", file.Path)
					}
				} else if entry.Data != nil {
					t.Fatalf("retained payload: %s", file.Path)
				}
			}
		})
	}
	if count < 8 {
		t.Fatalf("insufficient applicable directory cases: %d", count)
	}
}
