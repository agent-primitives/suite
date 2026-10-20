package agentsuite

import (
	"encoding/json"
	"strings"
	"testing"
)

var inventoryRequiredFields = []string{"path", "type", "mode", "uid", "gid"}

// inventoryPresenceFixture installs a bundled provider with a non-entrypoint data
// file and returns its provider path, raw document, and that file's raw entry.
// Mutating the entrypoint would let unrelated entrypoint errors mask acceptance.
func inventoryPresenceFixture(t *testing.T) (root, name string, document map[string]any, entry map[string]any) {
	t.Helper()
	root = writeMinimalSuite(t)
	addLargeDiffToolProvider(t, root, 1)
	name = "tool-providers/large/1.0.0/tool-provider.json"
	data := []byte("data")
	mustWriteMode(t, root, "tool-providers/large/1.0.0/linux-amd64/share/data", data, 0o644)
	document = presenceDocument(t, root, name)
	variant := document["variants"].([]any)[0].(map[string]any)
	entry = map[string]any{"path": "share/data", "type": "file", "mode": 0o644, "uid": 0, "gid": 0,
		"size": len(data), "digest": digestBytes(data), "component": "large"}
	variant["files"] = append(variant["files"].([]any), entry)
	return root, name, document, entry
}

// bindInventoryPresenceProvider recomputes the raw variant digest over the
// malformed document, so a stale digest cannot hide acceptance, then rebinds
// the provider and its ancestors.
func bindInventoryPresenceProvider(t *testing.T, root, name string, document map[string]any) {
	t.Helper()
	raw, err := json.Marshal(document)
	if err != nil {
		t.Fatal(err)
	}
	digests, err := rawVariantDigests(raw)
	if err != nil {
		t.Fatal(err)
	}
	document["variants"].([]any)[0].(map[string]any)["variantDigest"] = digests[0]
	bindPresenceProvider(t, root, name, document)
}

// Missing and null required inventory properties decode to Go zero values, which
// are also legitimate authored values (notably mode 0 and root ownership). The
// decoder must therefore see raw presence, just as schema and ValidateDirectory do.
func TestInventoryEntrySchemaDecoderAndDirectoryPresence(t *testing.T) {
	schema := compileReferenceSchema(t, "tool-provider.schema.json")
	t.Run("explicit zero mode is accepted", func(t *testing.T) {
		root, name, document, entry := inventoryPresenceFixture(t)
		entry["mode"] = 0
		bindInventoryPresenceProvider(t, root, name, document)
		validateSchemaJSON(t, schema, string(policyBindingRead(t, root, name)), true)
		assertPresenceDirectory(t, root, "")
	})
	for _, field := range inventoryRequiredFields {
		for _, kind := range []string{"missing", "null"} {
			t.Run(field+"/"+kind, func(t *testing.T) {
				root, name, document, entry := inventoryPresenceFixture(t)
				if kind == "missing" {
					delete(entry, field)
				} else {
					entry[field] = nil
				}
				bindInventoryPresenceProvider(t, root, name, document)
				validateSchemaJSON(t, schema, string(policyBindingRead(t, root, name)), false)

				// Decode the entry alone as well: through ToolProvider, the shared codec
				// already rejects null before any type-specific decoder can run.
				raw, err := json.Marshal(entry)
				if err != nil {
					t.Fatal(err)
				}
				want := `missing required field "` + field + `"`
				if kind == "null" {
					want = `field "` + field + `" must not be null`
				}
				var decoded InventoryEntry
				if err := json.Unmarshal(raw, &decoded); err == nil || !strings.Contains(err.Error(), want) {
					t.Errorf("encoding/json.Unmarshal(entry) = %v, want error containing %q", err, want)
				}
				var provider ToolProvider
				if err := Unmarshal(policyBindingRead(t, root, name), &provider); err == nil {
					t.Error("Unmarshal accepted malformed inventory entry")
				}
				if kind == "null" {
					want = `field "` + field + `": null is not allowed`
				}
				assertPresenceDirectory(t, root, want)
			})
		}
	}
}

func TestInventoryEntryDecoderAcceptsExplicitZerosAndStaysStrict(t *testing.T) {
	const valid = `{"path":"bin/tool","type":"directory","mode":0,"uid":0,"gid":0}`
	for _, tc := range []struct {
		name, raw, want string
	}{
		{"explicit zero mode uid gid", valid, ""},
		{"unknown property", strings.Replace(valid, "{", `{"unknown":false,`, 1), `unknown field "unknown"`},
		{"duplicate property", strings.Replace(valid, "{", `{"mode":0,`, 1), `duplicate JSON key "mode"`},
	} {
		t.Run(tc.name, func(t *testing.T) {
			var entry InventoryEntry
			err := Unmarshal([]byte(tc.raw), &entry)
			if tc.want == "" && err != nil || tc.want != "" && (err == nil || !strings.Contains(err.Error(), tc.want)) {
				t.Fatalf("Unmarshal = %v, want %q", err, tc.want)
			}
			var viaJSON InventoryEntry
			err = json.Unmarshal([]byte(tc.raw), &viaJSON)
			if tc.want == "" && err != nil || tc.want != "" && (err == nil || !strings.Contains(err.Error(), tc.want)) {
				t.Fatalf("encoding/json.Unmarshal = %v, want %q", err, tc.want)
			}
		})
	}
}
