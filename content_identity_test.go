package agentsuite

import (
	"archive/tar"
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

func writeIdentityFixture(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	// Literal bytes avoid platform checkout line-ending conversion.
	files := map[string]string{
		"agents/writer.json":                   "{\"id\":\"writer\",\"instructions\":{\"descriptor\":{\"digest\":\"sha256:516ff360a8ebb5e36e87f0d401a3cc7436ad2ad1059aae64670aff1078171df8\",\"mediaType\":\"text/markdown; charset=utf-8\",\"size\":15},\"path\":\"instructions/writer.md\"},\"mediaType\":\"application/vnd.agentsuite.agent.v1+json\",\"model\":{\"model\":\"example-model\",\"protocol\":\"openai-compatible\"},\"schemaVersion\":\"1.0.0-draft\"}",
		"agentsuite.json":                      "{\n  \"schemaVersion\": \"1.0.0-draft\",\n  \"mediaType\": \"application/vnd.agentsuite.manifest.v1+json\",\n  \"name\": \"minimal\",\n  \"agents\": [\n    {\n      \"id\": \"writer\",\n      \"path\": \"agents/writer.json\",\n      \"descriptor\": {\n        \"mediaType\": \"application/vnd.agentsuite.agent.v1+json\",\n        \"digest\": \"sha256:2fe4605b0a28a5cebebb3e351c7288cb9a1dee03205a5f380afbad2d735cc274\",\n        \"size\": 365\n      }\n    }\n  ],\n  \"toolProviderCatalog\": {\n    \"id\": \"catalog\",\n    \"path\": \"tool-providers/catalog.json\",\n    \"descriptor\": {\n      \"mediaType\": \"application/vnd.agentsuite.tool.provider.catalog.v1+json\",\n      \"digest\": \"sha256:933283a1fa90fd488db3f872fb89dc1572a5f638bf0a81514a542333e310ef95\",\n      \"size\": 121\n    }\n  },\n  \"compositions\": [\n    {\n      \"agent\": \"writer\",\n      \"platform\": {\n        \"os\": \"linux\",\n        \"architecture\": \"amd64\"\n      },\n      \"path\": \"compositions/writer-linux-amd64.json\",\n      \"descriptor\": {\n        \"mediaType\": \"application/vnd.agentsuite.composition.v1+json\",\n        \"digest\": \"sha256:c19a6173a3bad6723b5f4c36f49c8ee21afbd65317d9c9c4275ebd130b2223d5\",\n        \"size\": 202\n      }\n    }\n  ],\n  \"buildProfiles\": [\n    {\n      \"id\": \"default\",\n      \"path\": \"build-profiles/default.json\",\n      \"descriptor\": {\n        \"mediaType\": \"application/vnd.agentsuite.build.profile.v1+json\",\n        \"digest\": \"sha256:a7e6136d7e7daf2fcd7e61a149000382032dcbf140f2dda1076d2ee85d0a62cd\",\n        \"size\": 820\n      }\n    }\n  ]\n}\n",
		"build-profiles/default.json":          "{\"harness\":[{\"image\":{\"digest\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"mediaType\":\"application/vnd.oci.image.manifest.v1+json\",\"size\":1},\"imageRef\":\"registry.example/agentsuite/harness@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"platform\":{\"architecture\":\"amd64\",\"os\":\"linux\"}}],\"id\":\"default\",\"mediaType\":\"application/vnd.agentsuite.build.profile.v1+json\",\"runtimeBase\":[{\"image\":{\"digest\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"mediaType\":\"application/vnd.oci.image.manifest.v1+json\",\"size\":1},\"imageRef\":\"registry.example/agentsuite/runtime-base@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"platform\":{\"architecture\":\"amd64\",\"os\":\"linux\"}}],\"schemaVersion\":\"1.0.0-draft\",\"sourceEpoch\":1}",
		"compositions/writer-linux-amd64.json": "{\"agent\":\"writer\",\"buildProfile\":\"default\",\"mediaType\":\"application/vnd.agentsuite.composition.v1+json\",\"platform\":{\"architecture\":\"amd64\",\"os\":\"linux\"},\"schemaVersion\":\"1.0.0-draft\",\"toolProviders\":[]}",
		"instructions/writer.md":               "Write clearly.\n",
		"tool-providers/catalog.json":          "{\"mediaType\":\"application/vnd.agentsuite.tool.provider.catalog.v1+json\",\"schemaVersion\":\"1.0.0-draft\",\"toolProviders\":[]}",
	}
	for name, data := range files {
		mustWrite(t, root, name, []byte(data))
	}
	return root
}

func TestLooseDirectoryIdentityGolden(t *testing.T) {
	const golden = "sha256:15e0613bf11e7c70e2255a7f669381343656b0957a9231d0b92e189bf254f3fb"
	for _, mode := range []os.FileMode{0600, 0644, 0700, 0755} {
		t.Run(fmt.Sprintf("%o", mode), func(t *testing.T) {
			root := writeIdentityFixture(t)
			if err := filepath.WalkDir(root, func(name string, d os.DirEntry, err error) error {
				if err != nil {
					return err
				}
				if d.Type().IsRegular() {
					return os.Chmod(name, mode)
				}
				return nil
			}); err != nil {
				t.Fatal(err)
			}
			secureDirectoryFixture(t, root)
			if _, err := ValidateDirectory(root); err != nil {
				t.Fatal(err)
			}
			report, err := DiffPaths(root, root)
			if err != nil {
				t.Fatal(err)
			}
			if report.Before.ContentDigest != golden || report.After.ContentDigest != golden || report.HasChanges() {
				t.Fatalf("loose identity=%s / %s, changes=%v; want %s", report.Before.ContentDigest, report.After.ContentDigest, report.HasChanges(), golden)
			}
		})
	}
}

func TestLooseDirectoryDeclaredModeIgnoresHostMode(t *testing.T) {
	before, after := writeIdentityFixture(t), writeIdentityFixture(t)
	for _, root := range []string{before, after} {
		addLargeDiffToolProvider(t, root, 1)
	}
	file := filepath.Join(after, "tool-providers/large/1.0.0/linux-amd64/bin/tool-0000")
	if err := os.Chmod(file, 0600); err != nil {
		t.Fatal(err)
	}
	secureDirectoryFixture(t, before)
	secureDirectoryFixture(t, after)
	report, err := DiffPaths(before, after)
	if err != nil {
		t.Fatal(err)
	}
	if report.HasChanges() || report.Before.ContentDigest != report.After.ContentDigest {
		t.Fatalf("host permissions changed declared identity: %+v", report)
	}
}

func TestLooseDirectoryConflictingDeclarationsRefuse(t *testing.T) {
	root := writeIdentityFixture(t)
	addLargeDiffToolProvider(t, root, 1)
	secureDirectoryFixture(t, root)
	content, err := loadDirectory(root)
	if err != nil {
		t.Fatal(err)
	}
	v, _, err := validateContentGraph(content)
	if err != nil {
		t.Fatal(err)
	}
	variant := v.toolProviders["large@1.0.0"].Variants[0]
	variant.Files[0].Mode = 0700
	variant.VariantDigest = mustVariantDigest(t, variant)
	if err := validateVariant(variant, variant.VariantDigest, content); err == nil || !strings.Contains(err.Error(), "conflicting declared mode") {
		t.Fatalf("conflicting inventory mode: %v", err)
	}
}

func TestLooseDirectoryDeclaredDirectoryMetadata(t *testing.T) {
	root := writeIdentityFixture(t)
	addLargeDiffToolProvider(t, root, 1)
	secureDirectoryFixture(t, root)
	content, err := loadDirectory(root)
	if err != nil {
		t.Fatal(err)
	}
	v, _, err := validateContentGraph(content)
	if err != nil {
		t.Fatal(err)
	}
	variant := v.toolProviders["large@1.0.0"].Variants[0]
	variant.Files = append(variant.Files, InventoryEntry{Path: "bin", Type: "directory", Mode: 0700})
	variant.VariantDigest = mustVariantDigest(t, variant)
	if err := validateVariant(variant, variant.VariantDigest, content); err != nil {
		t.Fatal(err)
	}
}

func identityTar(t *testing.T, root string, mode int64) []byte {
	t.Helper()
	var names []string
	if err := filepath.WalkDir(root, func(name string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.Type().IsRegular() {
			rel, err := filepath.Rel(root, name)
			if err != nil {
				return err
			}
			names = append(names, filepath.ToSlash(rel))
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	sort.Strings(names)
	var buffer bytes.Buffer
	writer := tar.NewWriter(&buffer)
	for _, name := range names {
		data, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(name)))
		if err != nil {
			t.Fatal(err)
		}
		canonicalMode := int64(0644)
		if name == "instructions/writer.md" {
			canonicalMode = mode
		}
		if err := writer.WriteHeader(&tar.Header{Name: name, Typeflag: tar.TypeReg, Mode: canonicalMode, Size: int64(len(data))}); err != nil {
			t.Fatal(err)
		}
		if _, err := writer.Write(data); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	return buffer.Bytes()
}

func TestPublishedArtifactInventoryModesRemainExact(t *testing.T) {
	root := writeIdentityFixture(t)
	addLargeDiffToolProvider(t, root, 1)
	// The artifact declares a 0755 payload, but its actual tar entry is 0644.
	layout := writeTestOCILayoutTar(t, identityTar(t, root, 0644))
	if _, err := ValidatePath(layout); err == nil || !strings.Contains(err.Error(), "does not match payload metadata") {
		t.Fatalf("archive inventory mismatch: %v", err)
	}
}

func TestPublishedArtifactIdentityGolden(t *testing.T) {
	for _, test := range []struct {
		mode int64
		want string
	}{
		{0644, "sha256:15e0613bf11e7c70e2255a7f669381343656b0957a9231d0b92e189bf254f3fb"},
		{0600, "sha256:f1a58db4c473aef0154dfadb32e69bea3a39f707cef1670e84a57f517f06a65a"},
		{0755, "sha256:637aa13f65ac4a7944030a8e8057fbc3f0edc13a75fb261b30b103f9c7349325"},
	} {
		t.Run(fmt.Sprintf("%o", test.mode), func(t *testing.T) {
			layout := writeTestOCILayoutTar(t, identityTar(t, writeIdentityFixture(t), test.mode))
			report, err := DiffPaths(layout, layout)
			if err != nil {
				t.Fatal(err)
			}
			if report.Before.ContentDigest != test.want {
				t.Fatalf("artifact identity=%s, want %s", report.Before.ContentDigest, test.want)
			}
		})
	}
}
