package artifact

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"path/filepath"
	"testing"
)

func TestEmptyInventoryVariantIdentity(t *testing.T) {
	const emptyDigest = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
	variant := ToolProviderVariant{
		Platform: Platform{OS: "linux", Architecture: "amd64"}, VariantDigest: "ignored-old-digest",
		InstallRoot: "/opt/tool", PayloadRoot: "tool", Entrypoint: "/opt/tool/bin/empty",
		Runtime: RuntimeRequirement{ABI: "static", CPUBaseline: "x86-64-v1"},
		Files:   []InventoryEntry{{Path: "bin/empty", Type: "file", Mode: 0o755, Digest: emptyDigest}},
	}
	// Literal expected bytes establish both the zero property and exactly what
	// contributes to identity; no writer under test builds this expectation.
	const want = `{"entrypoint":"/opt/tool/bin/empty","files":[{"digest":"sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855","gid":0,"mode":493,"path":"bin/empty","size":0,"type":"file","uid":0}],"installRoot":"/opt/tool","payloadRoot":"tool","platform":{"architecture":"amd64","os":"linux"},"runtime":{"abi":"static","cpuBaseline":"x86-64-v1"},"variantDigest":""}`
	data, err := Marshal(struct {
		Variants []ToolProviderVariant `json:"variants"`
	}{[]ToolProviderVariant{variant}})
	if err != nil {
		t.Fatal(err)
	}
	digests, err := rawVariantDigests(data)
	if err != nil || len(digests) != 1 {
		t.Fatalf("variant digests: %v, %v", digests, err)
	}
	sum := sha256.Sum256([]byte(want))
	if expected := "sha256:" + hex.EncodeToString(sum[:]); digests[0] != expected {
		t.Fatalf("empty-file variant digest=%s, want %s", digests[0], expected)
	}
}

func TestEmptyInventoryPackageRoundTrip(t *testing.T) {
	root, name, document, entry := inventoryPresenceFixture(t)
	mustWriteMode(t, root, "tool-providers/large/1.0.0/linux-amd64/share/data", nil, 0o644)
	entry["size"], entry["digest"] = 0, digestBytes(nil)
	bindInventoryPresenceProvider(t, root, name, document)
	var provider ToolProvider
	readStrictJSON(t, filepath.Join(root, name), &provider)
	provider.Variants[0].VariantDigest = mustVariantDigest(t, provider.Variants[0])
	raw, err := Marshal(provider)
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(raw, &document); err != nil {
		t.Fatal(err)
	}
	bindPresenceProvider(t, root, name, document)
	if !bytes.Equal(raw, policyBindingRead(t, root, name)) {
		t.Fatal("pin refresh changed serialized provider bytes")
	}
	validateSchemaJSON(t, compileReferenceSchema(t, "tool-provider.schema.json"), string(raw), true)
	secureDirectoryFixture(t, root)
	if _, err := ValidatePath(root); err != nil {
		t.Fatalf("typed empty-file output and refreshed ancestors must validate: %v", err)
	}
}
