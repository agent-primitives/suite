package artifact

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// TestSharedDeclarationCases freezes ordinary agent and remote-provider
// declarations, not variant inventories, invocation closure, or other graph
// rules. Removing a semantic declaration check must fail both validation paths.
func TestSharedDeclarationCases(t *testing.T) {
	var corpus struct {
		Cases []struct {
			Name    string `json:"name"`
			Kind    string `json:"kind"`
			Bytes   string `json:"bytes"`
			Valid   *bool  `json:"valid"`
			Refusal string `json:"refusal"`
			Pointer string `json:"pointer"`
		} `json:"cases"`
	}
	readStrictJSON(t, "../../testdata/conformance/declaration-cases.json", &corpus)
	if len(corpus.Cases) != 23 {
		t.Fatal("truncated declaration corpus")
	}
	names := map[string]bool{}
	counts, positives := map[string]int{}, map[string]int{}
	for _, c := range corpus.Cases {
		requireDirectoryCaseName(t, names, "declaration", c.Name)
		if c.Kind != "agent" && c.Kind != "provider" && c.Kind != "suite" {
			t.Fatalf("unknown declaration kind %q", c.Kind)
		}
		if c.Valid == nil || !*c.Valid && (c.Refusal == "" || !strings.HasPrefix(c.Pointer, "/")) || *c.Valid && c.Refusal != "" {
			t.Fatalf("missing or inconsistent declaration expectations: %s", c.Name)
		}
		counts[c.Kind]++
		if *c.Valid {
			positives[c.Kind]++
		}
		t.Run(c.Name, func(t *testing.T) {
			raw, err := base64.StdEncoding.Strict().DecodeString(c.Bytes)
			if err != nil {
				t.Fatal(err)
			}
			if !bytes.Equal(raw, mustCanonicalizeJSON(t, raw)) {
				t.Fatal("declaration bytes are not stored canonical JSON")
			}
			root := writeMinimalSuite(t)
			name := "agents/writer.json"
			if c.Kind == "provider" {
				name = installPresenceRemoteProvider(t, root)
			} else if c.Kind == "suite" {
				name = "agentsuite.json"
			}
			secureDirectoryFixture(t, root)
			if _, err := ValidatePath(root); err != nil {
				t.Fatalf("base fixture must be valid: %v", err)
			}

			if c.Kind == "agent" {
				var suite Suite
				readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
				suite.Agents[0].Descriptor = Descriptor{MediaType: MediaTypeAgent, Digest: digestBytes(raw), Size: int64(len(raw))}
				mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
			} else if c.Kind == "provider" {
				// This existing helper refreshes the catalog and suite pins from
				// a raw map, without erasing malformed declaration fields via DTOs.
				// Install the authoritative literal bytes below, never its rewrite.
				var document map[string]any
				if err := json.Unmarshal(raw, &document); err != nil {
					t.Fatal(err)
				}
				if _, present := document["variants"]; present || document["remote"] == nil {
					t.Fatal("provider corpus must stay remote-only (no variant validation)")
				}
				bindPresenceProvider(t, root, name, document)
				if rebound := policyBindingRead(t, root, name); !bytes.Equal(rebound, raw) {
					t.Fatal("ancestor binding would change the frozen declaration identity")
				}
			}
			mustWrite(t, root, name, raw)
			stored, err := os.ReadFile(filepath.Join(root, name))
			if err != nil || !bytes.Equal(stored, raw) {
				t.Fatalf("fixture changed literal declaration bytes: %v", err)
			}
			secureDirectoryFixture(t, root)
			content, err := loadDirectory(root)
			if err != nil {
				t.Fatal(err)
			}
			var declarationErr error
			if c.Kind == "agent" {
				var agent Agent
				declarationErr = decodeStrict(raw, &agent)
				if declarationErr == nil {
					declarationErr = validateAgent(agent)
				}
			} else if c.Kind == "suite" {
				var suite Suite
				declarationErr = decodeStrict(raw, &suite)
				if declarationErr == nil {
					declarationErr = (&validator{suite: suite}).validateSuite()
				}
			} else {
				var provider ToolProvider
				declarationErr = decodeStrict(raw, &provider)
				if declarationErr == nil {
					declarationErr = validateToolProvider(provider, raw, content)
				}
			}
			check := func(stage string, err error) {
				t.Helper()
				if (err == nil) != *c.Valid {
					t.Errorf("%s valid=%t error=%v; want valid=%t (source %s%s)", stage, err == nil, err, *c.Valid, name, c.Pointer)
				}
				if !*c.Valid && (err == nil || !strings.Contains(err.Error(), c.Refusal)) {
					t.Errorf("%s missing intended declaration refusal %q at %s%s: %v", stage, c.Refusal, name, c.Pointer, err)
				}
			}
			check("decodeStrict + declaration validator", declarationErr)
			_, err = ValidatePath(root)
			check("ValidatePath", err)

			// These cases distinguish Go declaration semantics from shape-only
			// schema validation. Do not route product behavior by error text.
			switch c.Name {
			case "unsafe-model-endpoint-env":
				validateSchemaJSON(t, compileReferenceSchema(t, "agent.schema.json"), string(raw), true)
			case "duplicate-provider-tool-name", "case-insensitive-duplicate-remote-header":
				validateSchemaJSON(t, compileReferenceSchema(t, "tool-provider.schema.json"), string(raw), true)
			}
		})
	}
	if counts["agent"] != 11 || counts["provider"] != 11 || counts["suite"] != 1 || positives["agent"] != 3 || positives["provider"] != 1 {
		t.Fatal("declaration corpus population changed")
	}
}
