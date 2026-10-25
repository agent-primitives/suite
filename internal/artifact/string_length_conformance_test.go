package artifact

import (
	"path/filepath"
	"strings"
	"testing"
)

func TestSharedStringLengthCases(t *testing.T) {
	var corpus struct {
		Cases []struct {
			Name   string `json:"name"`
			Target string `json:"target"`
			Value  string `json:"value"`
			Omit   bool   `json:"omit,omitempty"`
			Valid  *bool  `json:"valid"`
		} `json:"cases"`
	}
	readStrictJSON(t, "../../testdata/conformance/string-length-cases.json", &corpus)
	names := map[string]bool{}
	counts := map[string]int{}
	if len(corpus.Cases) != 21 {
		t.Fatal("truncated string-length corpus")
	}
	for _, c := range corpus.Cases {
		requireDirectoryCaseName(t, names, "string-length", c.Name)
		if c.Valid == nil {
			t.Fatal("missing string-length validity")
		}
		counts[c.Target]++
		t.Run(c.Name, func(t *testing.T) {
			var err error
			switch c.Target {
			case "agentDescription":
				root := writeMinimalSuite(t)
				var suite Suite
				readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
				var agent Agent
				readStrictJSON(t, filepath.Join(root, "agents/writer.json"), &agent)
				agent.Description = c.Value
				suite.Agents[0].Descriptor = mustWriteJSON(t, root, "agents/writer.json", MediaTypeAgent, agent)
				mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
				secureDirectoryFixture(t, root)
				_, err = ValidatePath(root)
				if !*c.Valid && err != nil && !strings.Contains(err.Error(), "description must be at most 4096 characters") {
					t.Fatalf("wrong refusal: %v", err)
				}
			case "remoteHeaderName":
				fixture := copyAgentSuiteDirectory(t, "../../testdata/remote-mcp")
				secureDirectoryFixture(t, fixture)
				content, loadErr := loadDirectory(fixture)
				if loadErr != nil {
					t.Fatal(loadErr)
				}
				raw, loadErr := content.data("tool-provider.json")
				if loadErr != nil {
					t.Fatal(loadErr)
				}
				var provider ToolProvider
				if err := decodeStrict(raw, &provider); err != nil {
					t.Fatal(err)
				}
				provider.Remote.Headers[0].Name = c.Value
				raw, err = Marshal(provider)
				if err != nil {
					t.Fatal(err)
				}
				err = validateToolProvider(provider, raw, content)
			case "runtimeABIVersion", "inventoryComponent", "inventoryLinkTarget":
				root, name, document, entry := inventoryPresenceFixture(t)
				object, field := entry, "component"
				if c.Target == "runtimeABIVersion" {
					variant := document["variants"].([]any)[0].(map[string]any)
					object, field = variant["runtime"].(map[string]any), "abiVersion"
				} else if c.Target == "inventoryLinkTarget" {
					field = "linkTarget"
				}
				if c.Omit {
					delete(object, field)
				} else {
					object[field] = c.Value
				}
				bindInventoryPresenceProvider(t, root, name, document)
				secureDirectoryFixture(t, root)
				_, err = ValidatePath(root)
				if !*c.Valid && err != nil && !strings.Contains(err.Error(), field) {
					t.Fatalf("wrong optional-string refusal: %v", err)
				}
			default:
				t.Fatal("unknown string-length target")
			}
			if (err == nil) != *c.Valid {
				t.Fatalf("valid=%t error=%v; want valid=%t", err == nil, err, *c.Valid)
			}
			if c.Target == "remoteHeaderName" && !*c.Valid && !strings.Contains(err.Error(), "remote header") {
				t.Fatalf("wrong remote-header refusal: %v", err)
			}
		})
	}
	if counts["agentDescription"] != 9 || counts["remoteHeaderName"] != 4 || counts["runtimeABIVersion"] != 3 || counts["inventoryComponent"] != 3 || counts["inventoryLinkTarget"] != 2 {
		t.Fatal("missing string-length targets")
	}
}
