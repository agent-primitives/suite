package artifact

import (
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Frozen complete Go fixtures. All regular bytes, including small payloads,
// are available for public ValidatePath replay. This is test transport, not a
// change to production metadata retention. Metadata precedes inventory binding.
type sharedGraphCases struct {
	Cases []sharedGraphCase `json:"cases"`
}

type sharedGraphCase struct {
	Name       string             `json:"name"`
	Origin     string             `json:"origin"`
	SourceType string             `json:"sourceType"`
	Valid      *bool              `json:"valid"`
	Phase      string             `json:"phase"`
	Refusal    string             `json:"refusal"`
	FullPath   *bool              `json:"fullPath"`
	Entries    []sharedGraphEntry `json:"entries"`
}

type sharedGraphEntry struct {
	Path       string  `json:"path"`
	Type       string  `json:"type"`
	Mode       uint32  `json:"mode"`
	UID        int     `json:"uid"`
	GID        int     `json:"gid"`
	Size       int64   `json:"size"`
	Digest     string  `json:"digest"`
	LinkTarget string  `json:"linkTarget"`
	Bytes      *string `json:"bytes"`
}

func (row sharedGraphCase) content(t *testing.T) *contentSet {
	t.Helper()
	set := &contentSet{entries: map[string]contentEntry{}, folded: map[string]string{}}
	switch row.SourceType {
	case "directory":
		set.sourceType = "directory"
	case "archive": // Archive mode/ownership stay authoritative.
	default:
		t.Fatalf("unknown source type %q", row.SourceType)
	}
	previous := ""
	for _, e := range row.Entries {
		if e.Path <= previous {
			t.Fatal("entries must be strictly path-sorted")
		}
		previous = e.Path
		var data []byte
		if e.Bytes != nil {
			var err error
			data, err = base64.StdEncoding.Strict().DecodeString(*e.Bytes)
			if err != nil || int64(len(data)) != e.Size || digestBytes(data) != e.Digest {
				t.Fatalf("%s bytes do not match frozen metadata: %v", e.Path, err)
			}
		}
		if e.Type == "file" && e.Bytes == nil || e.Type != "file" && e.Bytes != nil {
			t.Fatalf("%s must retain exactly regular-file bytes", e.Path)
		}
		if e.Type != "file" && e.Type != "directory" {
			t.Fatalf("unexpected fixture entry type %q", e.Type)
		}
		if err := set.add(contentEntry{Path: e.Path, Type: e.Type, Mode: e.Mode,
			UID: e.UID, GID: e.GID, Size: e.Size, Digest: e.Digest,
			LinkTarget: e.LinkTarget, Data: data}); err != nil {
			t.Fatal(err)
		}
	}
	return set
}

// Invoke the ordinary graph phases themselves, omitting only policy and
// evaluation semantics (their declarations and pins remain in the documents).
// Stop at the first refusal so a downstream consequence cannot mask its phase.
func sharedGraphOutcome(content *contentSet) (string, error) {
	raw, err := content.data("agentsuite.json")
	if err != nil {
		return "loadSuite", err
	}
	var suite Suite
	if err := decodeStrict(raw, &suite); err != nil {
		return "loadSuite", err
	}
	v := &validator{content: content, suite: suite,
		agents: map[string]Agent{}, toolProviders: map[string]ToolProvider{},
		toolProviderDigests: map[string]string{}, builds: map[string]BuildProfile{},
		runtimes: map[string]RuntimeProfile{}, compositions: map[string]Composition{},
		toolProviderCompositions: map[string]ToolProviderComposition{}}
	for _, stage := range []struct {
		name string
		run  func() error
	}{
		{"loadSuite", v.validateSuite}, {"agents", v.loadAgents},
		{"providers", v.loadToolProviders}, {"builds", v.loadBuildProfiles},
		{"runtimes", v.loadRuntimeProfiles},
		{"providerCompositions", v.loadToolProviderCompositions},
		{"compositions", v.loadCompositions}, {"references", v.validateReferences},
	} {
		if err := stage.run(); err != nil {
			return stage.name, err
		}
	}
	return "", nil
}

func (row sharedGraphCase) fullValidatePath(t *testing.T) {
	t.Helper()
	if row.SourceType != "directory" {
		t.Fatal("fullPath requires a complete directory snapshot")
	}
	root := t.TempDir()
	for _, e := range row.Entries {
		if e.Type == "directory" {
			if err := os.MkdirAll(filepath.Join(root, filepath.FromSlash(e.Path)), 0o755); err != nil {
				t.Fatal(err)
			}
		} else {
			data, err := base64.StdEncoding.Strict().DecodeString(*e.Bytes)
			if err != nil {
				t.Fatal(err)
			}
			mustWrite(t, root, e.Path, data)
		}
	}
	secureDirectoryFixture(t, root)
	_, err := ValidatePath(root)
	if (err == nil) != *row.Valid || err != nil && !strings.Contains(err.Error(), row.Refusal) {
		t.Fatalf("ValidatePath error = %v; want valid=%t, refusal=%q", err, *row.Valid, row.Refusal)
	}
}

// Enforce the complete transport contract, including explicit false and zero
// fields. decodeStrict separately rejects unknown fields and wrong wire types.
func sharedGraphFields(t *testing.T, raw json.RawMessage, keys ...string) map[string]json.RawMessage {
	t.Helper()
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(raw, &fields); err != nil || len(fields) != len(keys) {
		t.Fatalf("incorrect corpus field set: %s (%v)", raw, err)
	}
	for _, key := range keys {
		if _, ok := fields[key]; !ok {
			t.Fatalf("missing corpus field %q", key)
		}
	}
	return fields
}

func TestSharedGraphCases(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "..", "testdata", "conformance", "graph-cases.json"))
	if err != nil {
		t.Fatal(err)
	}
	var corpus sharedGraphCases
	if err := decodeStrict(raw, &corpus); err != nil {
		t.Fatal(err)
	}
	root := sharedGraphFields(t, raw, "cases")
	var rows []json.RawMessage
	if err := json.Unmarshal(root["cases"], &rows); err != nil {
		t.Fatal(err)
	}
	names := map[string]bool{}
	fullPaths, archive := 0, 0
	for i, row := range corpus.Cases {
		fields := sharedGraphFields(t, rows[i], "name", "origin", "sourceType", "valid", "phase", "refusal", "fullPath", "entries")
		var entries []json.RawMessage
		if err := json.Unmarshal(fields["entries"], &entries); err != nil {
			t.Fatal(err)
		}
		for _, entry := range entries {
			sharedGraphFields(t, entry, "path", "type", "mode", "uid", "gid", "size", "digest", "linkTarget", "bytes")
		}
		if row.Name == "" || names[row.Name] || row.Origin == "" || row.Valid == nil || row.FullPath == nil || len(row.Entries) == 0 {
			t.Fatalf("incomplete or duplicate case %q", row.Name)
		}
		names[row.Name] = true
		if *row.FullPath {
			fullPaths++
		} else if row.SourceType != "archive" {
			t.Fatal("complete directory cases must exercise ValidatePath")
		}
		if row.SourceType == "archive" {
			archive++
		}
		t.Run(row.Name, func(t *testing.T) {
			phase, err := sharedGraphOutcome(row.content(t))
			refusal := ""
			if err != nil {
				refusal = err.Error()
			}
			if (err == nil) != *row.Valid || phase != row.Phase || refusal != row.Refusal {
				t.Fatalf("phase=%q error=%v; want valid=%t phase=%q refusal=%q", phase, err, *row.Valid, row.Phase, row.Refusal)
			}
			if *row.FullPath {
				row.fullValidatePath(t)
			}
		})
	}
	if len(corpus.Cases) != 71 || fullPaths != 69 || archive != 2 {
		t.Fatalf("corpus counts cases/fullPath/archive = %d/%d/%d, want 71/69/2", len(corpus.Cases), fullPaths, archive)
	}
	for _, name := range []string{"minimal", "composition-providers-omitted", "composition-providers-null", "coordinator", "remote", "bundled", "runtime-two-profiles", "shared-provider", "standalone", "retained-true", "dependency-inward", "unselected-variant-dependency", "sorted-resolutions", "standalone-collision"} {
		if !names[name] {
			t.Fatalf("required fixture %q missing", name)
		}
	}
}
