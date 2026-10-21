package artifact

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLegacyDraftVersionGrammar(t *testing.T) {
	// Pin observable legacy acceptance, not a second implementation of the regex.
	// Full SemVer must not replace this grammar for received draft documents.
	schema := compileReferenceSchema(t, "tool-provider.schema.json")
	for _, tc := range []struct {
		version string
		valid   bool
	}{
		{"1.0.0", true},
		{"01.02.003", true},
		{"1.0.0-01", true},
		{"1.0.0-.", true},
		{"1.0.0+..", true},
		{"1.0.0-alpha..1", true},
		{"1.0.0-rc.1", true},
		{"1.0.0+build", true},
		{"1.0.0-alpha+build", false},
		{"1.0.0-alpha.1+build.7", false},
		{"v1.0.0", false},
		{"1.0", false},
		{"1.0.0-", false},
	} {
		t.Run(tc.version, func(t *testing.T) {
			root := copyAgentSuiteDirectory(t, "../../testdata/minimal")
			oldPath := installPresenceRemoteProvider(t, root)
			if _, err := ValidatePath(root); err != nil {
				t.Fatalf("draft positive control: %v", err)
			}
			document := presenceDocument(t, root, oldPath)
			validateSchemaJSON(t, schema, string(policyBindingRead(t, root, oldPath)), true)
			document["version"] = tc.version

			// Keep the provider, catalog selector and all descriptor ancestors in
			// agreement, so a refusal is about grammar rather than stale identity.
			newPath := "tool-providers/search/" + tc.version + "/tool-provider.json"
			var catalog ToolProviderCatalog
			readStrictJSON(t, filepath.Join(root, "tool-providers/catalog.json"), &catalog)
			for i := range catalog.ToolProviders {
				if catalog.ToolProviders[i].Path == oldPath {
					catalog.ToolProviders[i].Version = tc.version
					catalog.ToolProviders[i].Path = newPath
				}
			}
			mustWriteJSON(t, root, "tool-providers/catalog.json", MediaTypeToolProviderCatalog, catalog)
			bindPresenceProvider(t, root, newPath, document)
			if newPath != oldPath {
				if err := os.Remove(filepath.Join(root, oldPath)); err != nil {
					t.Fatal(err)
				}
			}

			validateSchemaJSON(t, schema, string(policyBindingRead(t, root, newPath)), tc.valid)
			report, err := ValidatePath(root)
			if tc.valid {
				if err != nil {
					t.Fatalf("legacy draft version rejected: %v", err)
				}
				if report.ToolProviders != 1 {
					t.Fatalf("tool providers = %d, want 1", report.ToolProviders)
				}
			} else if err == nil || !strings.Contains(err.Error(), "invalid identity or exact version") {
				t.Fatalf("ValidatePath = %v, want exact-version refusal", err)
			}
		})
	}
}

func TestLegacyDraftReaderBoundary(t *testing.T) {
	for _, tc := range []struct {
		name, version, extra, want string
	}{
		{"literal draft", "1.0.0-draft", "", ""},
		{"stable is not an alias", "1.0.0", "", "schemaVersion must be"},
		{"draft-like is not an alias", "1.0.0-draft.1", "", "schemaVersion must be"},
		{"unknown optional field", "1.0.0-draft", `"futureOptional":false,`, "unknown field"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			root := copyAgentSuiteDirectory(t, "../../testdata/minimal")
			name := filepath.Join(root, "agentsuite.json")
			raw, err := os.ReadFile(name)
			if err != nil {
				t.Fatal(err)
			}
			if bytes.Count(raw, []byte(`"1.0.0-draft"`)) != 1 {
				t.Fatal("positive control must contain one literal draft root version")
			}
			if _, err := ValidatePath(root); err != nil {
				t.Fatalf("draft positive control: %v", err)
			}
			candidate := strings.Replace(string(raw), `"1.0.0-draft"`, `"`+tc.version+`"`, 1)
			candidate = strings.Replace(candidate, "{", "{"+tc.extra, 1)
			mustWrite(t, root, "agentsuite.json", []byte(candidate))
			_, err = ValidatePath(root)
			if tc.want == "" {
				if err != nil {
					t.Fatalf("literal draft rejected: %v", err)
				}
				after, err := os.ReadFile(name)
				if err != nil {
					t.Fatal(err)
				}
				if !bytes.Equal(after, raw) {
					t.Fatal("validation rewrote received draft bytes")
				}
			} else if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("ValidatePath = %v, want refusal containing %q", err, tc.want)
			}
		})
	}
}
