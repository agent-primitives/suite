package artifact

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestExtensionSchemaAndDirectoryPresence(t *testing.T) {
	for _, target := range []string{"suite", "provider", "agent"} {
		for _, tc := range []struct {
			name, extension, want string
			schemaValid           bool
		}{
			{"missing critical", `[{"name":"future"}]`, "critical", false},
			{"null critical", `[{"name":"future","critical":null}]`, "critical", false},
			{"explicit false", `[{"name":"future","critical":false}]`, "", true},
			{"unsupported true", `[{"name":"future","critical":true}]`, "unknown critical extension", true},
		} {
			t.Run(target+"/"+tc.name, func(t *testing.T) {
				root := writeMinimalSuite(t)
				name, schemaName := "agentsuite.json", "suite.schema.json"
				if target == "provider" {
					name = installPresenceRemoteProvider(t, root)
					schemaName = "tool-provider.schema.json"
				} else if target == "agent" {
					name, schemaName = "agents/writer.json", "agent.schema.json"
				}
				document := presenceDocument(t, root, name)
				document["extensions"] = json.RawMessage(tc.extension)
				mustWriteJSON(t, root, name, "", document)
				want, valid := tc.want, tc.schemaValid
				if target == "provider" {
					bindPresenceProvider(t, root, name, document)
				} else if target == "agent" {
					bindPolicyAgent(t, root, "writer", func(agent map[string]any) {
						agent["extensions"] = json.RawMessage(tc.extension)
					})
					// Agent's schema does not constrain extension records. Keep its
					// existing missing-critical acceptance and null-critical refusal.
					valid = true
					if tc.name == "missing critical" {
						want = ""
					}
				}
				validateSchemaJSON(t, compileReferenceSchema(t, schemaName), string(policyBindingRead(t, root, name)), valid)
				assertPresenceDirectory(t, root, want)
			})
		}
	}
}

func TestToolProviderSchemaAndDirectoryPresence(t *testing.T) {
	for _, tc := range []struct {
		name, variants, output, want string
		schemaValid                  bool
	}{
		{"remote omitted variants", "", "keep", "", true},
		{"remote empty variants", `[]`, "keep", "variants", false},
		{"remote null variants", `null`, "keep", "variants", false},
		{"omitted output schema", "", "omit", "", true},
		{"null output schema", "", `null`, "outputSchema", false},
		{"object output schema", "", "keep", "", true},
		{"output descriptor checked", "", "bad digest", "referenced file is absent or has a different digest", true},
		{"remote and bundled variants", "bundled", "keep", "", true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			root := writeMinimalSuite(t)
			name := installPresenceRemoteProvider(t, root)
			if tc.variants == "bundled" {
				addLargeDiffToolProvider(t, root, 1)
				name = "tool-providers/large/1.0.0/tool-provider.json"
			}
			document := presenceDocument(t, root, name)
			if tc.variants == "bundled" {
				remote := presenceDocument(t, root, "tool-providers/search/1.0.0/tool-provider.json")
				document["remote"] = remote["remote"]
			} else if tc.variants != "" {
				document["variants"] = json.RawMessage(tc.variants)
			}
			tools := document["tools"].([]any)
			tool := tools[0].(map[string]any)
			switch tc.output {
			case "omit":
				delete(tool, "outputSchema")
			case `null`:
				tool["outputSchema"] = nil
			case "bad digest":
				tool["outputSchema"].(map[string]any)["descriptor"].(map[string]any)["digest"] = "sha256:" + strings.Repeat("0", 64)
			}
			bindPresenceProvider(t, root, name, document)
			validateSchemaJSON(t, compileReferenceSchema(t, "tool-provider.schema.json"), string(policyBindingRead(t, root, name)), tc.schemaValid)
			assertPresenceDirectory(t, root, tc.want)
		})
	}
}

func TestToolProviderJSONDecoderStrictness(t *testing.T) {
	fixture, err := os.ReadFile("../../testdata/remote-mcp/tool-provider.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		name, extra string
		valid       bool
	}{
		{"valid", "", true},
		{"unknown property", `"unknown":false,`, false},
		{"duplicate property", `"id":"search",`, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			raw := strings.Replace(string(fixture), "{", "{"+tc.extra, 1)
			var provider ToolProvider
			if err := json.Unmarshal([]byte(raw), &provider); (err == nil) != tc.valid {
				t.Fatalf("encoding/json.Unmarshal = %v, want valid=%v", err, tc.valid)
			}
		})
	}
}

func presenceDocument(t *testing.T, root, name string) map[string]any {
	t.Helper()
	var document map[string]any
	if err := json.Unmarshal(policyBindingRead(t, root, name), &document); err != nil {
		t.Fatal(err)
	}
	return document
}

func installPresenceRemoteProvider(t *testing.T, root string) string {
	t.Helper()
	for _, name := range []string{"search-input.json", "search-output.json", "flag-result-input.json", "flag-result-output.json"} {
		data, err := os.ReadFile(filepath.Join("../../testdata", "remote-mcp", "schemas", name))
		if err != nil {
			t.Fatal(err)
		}
		mustWrite(t, root, "schemas/"+name, data)
	}
	name := "tool-providers/search/1.0.0/tool-provider.json"
	provider := presenceDocument(t, "../../testdata/remote-mcp", "tool-provider.json")
	var catalog ToolProviderCatalog
	readStrictJSON(t, filepath.Join(root, "tool-providers/catalog.json"), &catalog)
	catalog.ToolProviders = append(catalog.ToolProviders, ManifestRef{ID: "search", Version: "1.0.0", Path: name,
		Descriptor: mustWriteJSON(t, root, name, MediaTypeToolProvider, provider)})
	mustWriteJSON(t, root, "tool-providers/catalog.json", MediaTypeToolProviderCatalog, catalog)
	bindPresenceProvider(t, root, name, provider)
	return name
}

// Rebind the raw document and every ancestor without decoding the malformed
// provider into public types (which would erase precisely the fields under test).
func bindPresenceProvider(t *testing.T, root, name string, document map[string]any) {
	t.Helper()
	descriptor := mustWriteJSON(t, root, name, MediaTypeToolProvider, document)
	var catalog ToolProviderCatalog
	readStrictJSON(t, filepath.Join(root, "tool-providers/catalog.json"), &catalog)
	for i := range catalog.ToolProviders {
		if catalog.ToolProviders[i].Path == name {
			catalog.ToolProviders[i].Descriptor = descriptor
		}
	}
	var suite Suite
	readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
	suite.ToolProviderCatalog.Descriptor = mustWriteJSON(t, root, "tool-providers/catalog.json", MediaTypeToolProviderCatalog, catalog)
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
}

func assertPresenceDirectory(t *testing.T, root, want string) {
	t.Helper()
	_, err := ValidateDirectory(root)
	if want == "" {
		if err != nil {
			t.Fatalf("ValidateDirectory: %v", err)
		}
	} else if err == nil || !strings.Contains(err.Error(), want) {
		t.Fatalf("ValidateDirectory = %v, want error containing %q", err, want)
	}
}
