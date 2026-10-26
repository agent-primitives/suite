package artifact

import (
	"archive/tar"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"testing"
)

// Compact, test-only byte transport: prefix + block*repeat + suffix.
// The bounds below protect fixture expansion, not the accepted package format.
type sharedLiteralCase struct {
	Name       string `json:"name"`
	Target     string `json:"target"`
	Path       string `json:"path"`
	Prefix     string `json:"prefix"`
	Block      string `json:"block"`
	Repeat     int    `json:"repeat"`
	Suffix     string `json:"suffix"`
	Size       int64  `json:"size"`
	Digest     string `json:"digest"`
	RootDigest string `json:"rootDigest"`
}

func (row sharedLiteralCase) body(t *testing.T) []byte {
	t.Helper()
	const maxFixtureBytes = 5 << 20
	if row.Repeat < 0 || row.Repeat > maxFixtureBytes || row.Size < 0 || row.Size > maxFixtureBytes {
		t.Fatal("literal fixture expansion exceeds its test-only bounds")
	}
	parts := make([][]byte, 3)
	for i, encoded := range []string{row.Prefix, row.Block, row.Suffix} {
		data, err := base64.StdEncoding.Strict().DecodeString(encoded)
		if err != nil || len(data) > 1024 {
			t.Fatalf("invalid or oversized literal transport part %d: %v", i, err)
		}
		parts[i] = data
	}
	size := int64(len(parts[0])) + int64(len(parts[1]))*int64(row.Repeat) + int64(len(parts[2]))
	if size != row.Size {
		t.Fatalf("expanded size = %d, want %d", size, row.Size)
	}
	body := make([]byte, 0, int(size))
	body = append(body, parts[0]...)
	body = append(body, bytes.Repeat(parts[1], row.Repeat)...)
	body = append(body, parts[2]...)
	if digestBytes(body) != row.Digest {
		t.Fatal("expanded bytes do not match the frozen literal digest")
	}
	return body
}

func (row sharedLiteralCase) fullValidatePath(t *testing.T) {
	t.Helper()
	root := writeMinimalSuite(t)
	body := row.body(t)
	mustWrite(t, root, row.Path, body)
	ref := FileRef{Path: row.Path, Descriptor: Descriptor{
		MediaType: MediaTypeInstructions, Digest: row.Digest, Size: row.Size,
	}}
	switch row.Target {
	case "instructions":
		var agent Agent
		readStrictJSON(t, filepath.Join(root, "agents/writer.json"), &agent)
		agent.Instructions = ref
		var suite Suite
		readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
		suite.Agents[0].Descriptor = mustWriteJSON(t, root, "agents/writer.json", MediaTypeAgent, agent)
		mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
	case "inputSchema", "outputSchema":
		if !json.Valid(body) {
			t.Fatal("schema fixture must contain valid JSON without canonicalizing its bytes")
		}
		name := installPresenceRemoteProvider(t, root)
		provider := presenceDocument(t, root, name)
		ref.Descriptor.MediaType = MediaTypeJSONSchema
		provider["tools"].([]any)[0].(map[string]any)[row.Target] = ref
		bindPresenceProvider(t, root, name, provider)
	default:
		t.Fatalf("unknown literal target %q", row.Target)
	}

	// Full ordinary validation must succeed on both native directory and OCI
	// paths before the root JCS identity is computed or compared.
	secureDirectoryFixture(t, root)
	if !t.Run("directory", func(t *testing.T) {
		if _, err := ValidatePath(root); err != nil {
			t.Fatalf("ValidatePath(directory): %v", err)
		}
	}) {
		return
	}
	ociRoot := writeTestOCILayoutTar(t, literalPortableTar(t, root))
	secureDirectoryFixture(t, ociRoot)
	if !t.Run("oci", func(t *testing.T) {
		if _, err := ValidatePath(ociRoot); err != nil {
			t.Fatalf("ValidatePath(OCI): %v", err)
		}
	}) {
		return
	}
	stored, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(row.Path)))
	if err != nil || !bytes.Equal(stored, body) {
		t.Fatalf("literal bytes changed: %v", err)
	}
	raw, err := os.ReadFile(filepath.Join(root, "agentsuite.json"))
	if err != nil {
		t.Fatal(err)
	}
	got, err := canonicalDigest(raw)
	if err != nil {
		t.Fatal(err)
	}
	if got != row.RootDigest {
		t.Fatalf("validated Go root digest = %q, want frozen %q", got, row.RootDigest)
	}
}

// Windows host permissions are not portable archive modes. These fixtures have
// no executable payloads: author their archive modes instead of copying 0666.
func literalPortableTar(t *testing.T, root string) []byte {
	t.Helper()
	reader := tar.NewReader(bytes.NewReader(tarDirectory(t, root)))
	var buffer bytes.Buffer
	writer := tar.NewWriter(&buffer)
	for {
		header, err := reader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		header.Mode = 0o644
		if header.Typeflag == tar.TypeDir {
			header.Mode = 0o755
		}
		if err := writer.WriteHeader(header); err != nil {
			t.Fatal(err)
		}
		if _, err := io.Copy(writer, reader); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	return buffer.Bytes()
}

func TestSharedLiteralPortableModes(t *testing.T) {
	root := t.TempDir()
	body := []byte("literal bytes")
	mustWriteMode(t, root, "data/value.raw", body, 0o666)
	reader := tar.NewReader(bytes.NewReader(literalPortableTar(t, root)))
	for {
		header, err := reader.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		want := int64(0o644)
		if header.Typeflag == tar.TypeDir {
			want = 0o755
		} else {
			got, err := io.ReadAll(reader)
			if err != nil || !bytes.Equal(got, body) {
				t.Fatalf("literal bytes changed: %v", err)
			}
		}
		if header.Mode != want {
			t.Fatalf("archive mode = %o, want %o", header.Mode, want)
		}
	}
}

func TestSharedLiteralCases(t *testing.T) {
	raw, err := os.ReadFile("../../testdata/conformance/literal-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var corpus struct {
		Cases []sharedLiteralCase `json:"cases"`
	}
	if err := decodeStrict(raw, &corpus); err != nil {
		t.Fatal(err)
	}
	fields := sharedGraphFields(t, raw, "cases")
	var rows []json.RawMessage
	if err := json.Unmarshal(fields["cases"], &rows); err != nil {
		t.Fatal(err)
	}
	if len(corpus.Cases) != 6 {
		t.Fatalf("literal case count = %d, want 6", len(corpus.Cases))
	}
	names, paths := map[string]bool{}, map[string]bool{}
	targets := map[string]int{}
	for i, row := range corpus.Cases {
		fields := sharedGraphFields(t, rows[i], "name", "target", "path", "prefix", "block", "repeat", "suffix", "size", "digest", "rootDigest")
		for key, value := range fields {
			if bytes.Equal(value, []byte("null")) {
				t.Fatalf("literal field %q cannot be null", key)
			}
		}
		if row.Name == "" || names[row.Name] || paths[row.Path] || !IsValidDigest(row.RootDigest) {
			t.Fatalf("incomplete or duplicate literal case %q", row.Name)
		}
		if _, err := validateContentPath(row.Path); err != nil {
			t.Fatal(err)
		}
		names[row.Name], paths[row.Path] = true, true
		targets[row.Target]++
		t.Run(row.Name, func(t *testing.T) { row.fullValidatePath(t) })
	}
	if targets["instructions"] != 3 || targets["inputSchema"] != 2 || targets["outputSchema"] != 1 {
		t.Fatalf("unexpected literal targets: %v", targets)
	}
}

// The Python fixture builder can replay graph-cases.json's minimal row,
// rather than approximating Go's helper or using testdata/minimal.
func TestSharedLiteralBase(t *testing.T) {
	root := writeMinimalSuite(t)
	raw, err := os.ReadFile(filepath.Join(root, "agentsuite.json"))
	if err != nil {
		t.Fatal(err)
	}
	const want = "sha256:054f6c9a298c3fa102261d3c11776182e2588c77ca522b09a80a66b84f9eef32"
	got, err := canonicalDigest(raw)
	if err != nil || got != want {
		t.Fatalf("writeMinimalSuite root = %q (%v), want graph corpus minimal %q", got, err, want)
	}
}
