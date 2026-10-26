package artifact

import (
	"archive/tar"
	"bytes"
	"encoding/base64"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

type readerBoundaryCase struct {
	sharedGraphCase
	Control string `json:"control"`
	Body    *struct {
		Path   string `json:"path"`
		Block  string `json:"block"`
		Repeat int    `json:"repeat"`
	} `json:"body"`
}
type readerBoundaryCorpus struct {
	Controls []sharedGraphCase    `json:"controls"`
	Cases    []readerBoundaryCase `json:"cases"`
}

func boundaryBytes(t *testing.T, row readerBoundaryCase, e sharedGraphEntry) []byte {
	t.Helper()
	if e.Type != "file" {
		if e.Bytes != nil || e.Size != 0 || e.Digest != "" {
			t.Fatal("link/directory has bytes")
		}
		return nil
	}
	var data []byte
	var err error
	if e.Bytes != nil {
		data, err = base64.StdEncoding.Strict().DecodeString(*e.Bytes)
	} else {
		if row.Body == nil || row.Body.Path != e.Path || row.Body.Block != "IA==" || row.Body.Repeat != maxJSONBytes+1 {
			t.Fatal("invalid compact body")
		}
		data = bytes.Repeat([]byte(" "), row.Body.Repeat)
	}
	if err != nil || int64(len(data)) != e.Size || digestBytes(data) != e.Digest {
		t.Fatalf("%s: byte identity mismatch: %v", e.Path, err)
	}
	return data
}

// Author archive headers from frozen metadata, never host permissions or extraction.
func boundaryTar(t *testing.T, row readerBoundaryCase) []byte {
	t.Helper()
	var buffer bytes.Buffer
	out := tar.NewWriter(&buffer)
	for _, e := range row.Entries {
		data := boundaryBytes(t, row, e)
		flag, ok := map[string]byte{"file": tar.TypeReg, "directory": tar.TypeDir, "symlink": tar.TypeSymlink, "hardlink": tar.TypeLink}[e.Type]
		if !ok || e.UID != 0 || e.GID != 0 {
			t.Fatal("invalid boundary metadata")
		}
		h := &tar.Header{Name: e.Path, Typeflag: flag, Mode: int64(e.Mode), Size: e.Size, Linkname: e.LinkTarget, ModTime: time.Unix(0, 0)}
		if err := out.WriteHeader(h); err != nil {
			t.Fatal(err)
		}
		if _, err := out.Write(data); err != nil {
			t.Fatal(err)
		}
	}
	if err := out.Close(); err != nil {
		t.Fatal(err)
	}
	return buffer.Bytes()
}

func TestSharedReaderBoundaryCases(t *testing.T) {
	raw, err := os.ReadFile("../../testdata/conformance/reader-boundary-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var corpus readerBoundaryCorpus
	if err := decodeStrict(raw, &corpus); err != nil {
		t.Fatal(err)
	}
	if len(corpus.Controls) != 2 || len(corpus.Cases) != 5 {
		t.Fatal("boundary populations must be 2 controls/5 refusals")
	}
	controls := map[string]bool{}
	for _, control := range corpus.Controls {
		if control.Valid == nil || !*control.Valid || controls[control.Name] {
			t.Fatal("invalid control")
		}
		control.fullValidatePath(t)
		source := writeTestOCILayoutTar(t, boundaryTar(t, readerBoundaryCase{sharedGraphCase: control}))
		if _, err := ValidatePath(source); err != nil {
			t.Fatal(err)
		}
		controls[control.Name] = true
	}
	names := map[string]bool{}
	for _, row := range corpus.Cases {
		t.Run(row.Name, func(t *testing.T) {
			if !controls[row.Control] || names[row.Name] || row.Valid == nil || *row.Valid || row.Refusal == "" || row.Phase != "ValidatePath" || !strings.HasPrefix(row.Origin, "d753475d3313507bb3297d06b28ec373287e3791:") {
				t.Fatal("invalid boundary row")
			}
			names[row.Name] = true
			source := writeTestOCILayoutTar(t, boundaryTar(t, row))
			if _, err := ValidatePath(source); err == nil || !strings.Contains(err.Error(), row.Refusal) {
				t.Fatalf("OCI error=%v; want %q", err, row.Refusal)
			}
			// Windows does not require native symlink privileges; archived rows still run.
			if row.SourceType == "archive" || runtime.GOOS == "windows" && row.Body == nil {
				return
			}
			root := t.TempDir()
			for _, e := range row.Entries {
				target := filepath.Join(root, filepath.FromSlash(e.Path))
				switch e.Type {
				case "directory":
					err = os.MkdirAll(target, 0o755)
				case "file":
					mustWrite(t, root, e.Path, boundaryBytes(t, row, e))
				case "symlink":
					err = os.Symlink(filepath.FromSlash(e.LinkTarget), target)
				default:
					t.Fatal("unexpected native entry type")
				}
				if err != nil {
					t.Fatal(err)
				}
			}
			secureDirectoryFixture(t, root)
			if _, err := ValidatePath(root); err == nil || !strings.Contains(err.Error(), row.Refusal) {
				t.Fatalf("directory error=%v; want %q", err, row.Refusal)
			}
		})
	}
	for _, name := range []string{"policy-oversized", "policy-symlink-root", "policy-symlink-writer", "policy-symlink-extra", "policy-hardlink-writer"} {
		if !names[name] {
			t.Fatalf("missing boundary %s", name)
		}
	}
}
