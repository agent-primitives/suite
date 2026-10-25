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

func TestSharedDocumentShapeCases(t *testing.T) {
	var corpus struct {
		Cases []struct {
			Name       string `json:"name"`
			Fixture    string `json:"fixture"`
			File       string `json:"file"`
			Schema     string `json:"schema"`
			Bytes      string `json:"bytes"`
			Valid      *bool  `json:"valid"`
			Regression *bool  `json:"regression"`
			Refusal    string `json:"refusal"`
			Pointer    string `json:"pointer"`
		} `json:"cases"`
	}
	readStrictJSON(t, "../../testdata/conformance/document-shape-cases.json", &corpus)
	if len(corpus.Cases) != 32 {
		t.Fatal("truncated document-shape corpus")
	}
	names := map[string]bool{}
	valid, regressions := 0, 0
	for _, c := range corpus.Cases {
		requireDirectoryCaseName(t, names, "document-shape", c.Name)
		if c.Valid == nil || c.Regression == nil || !*c.Valid && c.Refusal == "" {
			t.Fatal("missing document-shape expectations")
		}
		if *c.Valid {
			valid++
		}
		if *c.Regression {
			if *c.Valid {
				t.Fatal("regression must be a refusal")
			}
			regressions++
		}
		t.Run(c.Name, func(t *testing.T) {
			var root, name, schema string
			switch c.Fixture {
			case "agent":
				root, name, schema = writeMinimalSuite(t), "agents/writer.json", "agent.schema.json"
			case "suite":
				root, name, schema = writeMinimalSuite(t), "agentsuite.json", "suite.schema.json"
			case "provider", "inventory":
				root, name, _, _ = inventoryPresenceFixture(t)
				schema = "tool-provider.schema.json"
				if c.Fixture == "inventory" {
					mustWriteMode(t, root, "tool-providers/large/1.0.0/linux-amd64/share/data", nil, 0o644)
				}
			case "remote":
				root = writeMinimalSuite(t)
				name, schema = installPresenceRemoteProvider(t, root), "tool-provider.schema.json"
			default:
				t.Fatal("unknown document-shape fixture")
			}
			if c.File != name || c.Schema != schema {
				t.Fatal("document-shape source/schema mismatch")
			}
			raw, err := base64.StdEncoding.DecodeString(c.Bytes)
			if err != nil {
				t.Fatal(err)
			}
			switch c.Fixture {
			case "suite":
				mustWrite(t, root, name, raw)
			case "agent":
				var suite Suite
				readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
				mustWrite(t, root, name, raw)
				suite.Agents[0].Descriptor = Descriptor{MediaType: MediaTypeAgent, Digest: digestBytes(raw), Size: int64(len(raw))}
				mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
			default:
				// Keep the frozen child and raw variant digest intact. Only rebind
				// its ancestors, without decoding the malformed child into a DTO.
				var document map[string]any
				if err := json.Unmarshal(raw, &document); err != nil {
					t.Fatal(err)
				}
				bindPresenceProvider(t, root, name, document)
			}
			stored, err := os.ReadFile(filepath.Join(root, name))
			if err != nil || !bytes.Equal(stored, raw) {
				t.Fatalf("fixture changed literal input bytes: %v", err)
			}
			secureDirectoryFixture(t, root)
			_, err = ValidatePath(root)
			if (err == nil) != *c.Valid {
				t.Fatalf("valid=%t error=%v; want valid=%t", err == nil, err, *c.Valid)
			}
			if !*c.Valid && !strings.Contains(err.Error(), c.Refusal) {
				t.Fatalf("wrong refusal, want field %q: %v", c.Refusal, err)
			}
		})
	}
	if valid != 5 || regressions != 25 {
		t.Fatal("document-shape population changed")
	}
}
