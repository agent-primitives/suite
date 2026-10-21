package artifact

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestPolicyBindingFixtureConformance(t *testing.T) {
	root := "../../testdata/policy-binding"
	for _, source := range []string{root, writeTestOCILayout(t, root)} {
		if _, err := ValidatePath(source); err != nil {
			t.Fatalf("policy-binding fixture: %v", err)
		}
	}
	data, err := os.ReadFile(root + "/agents/writer.json")
	if err != nil {
		t.Fatal(err)
	}
	validateSchemaJSON(t, compileReferenceSchema(t, "agent.schema.json"), string(data), true)
}

func TestPolicyBindingRejectsOCIHardlink(t *testing.T) {
	root, ref := writePolicyBindingSuite(t, bindingMediaV1, []byte(bindingV1))
	// The target sorts before policies/ so this is a valid archive hardlink,
	// not a loader rejection caused by an unresolved target.
	target := "metadata/original.json"
	mustWrite(t, root, target, []byte(bindingV1))
	if _, err := ValidateDirectory(root); err != nil {
		t.Fatalf("regular-file control: %v", err)
	}
	layout := writeTestOCILayoutTar(t, tarDirectoryWithHardlink(t, root, ref.Path, target))
	if _, err := ValidatePath(layout); err == nil || !strings.Contains(err.Error(), "not a regular file") {
		t.Fatalf("archive hardlink policy: %v", err)
	}
}

func TestAgentPolicyReferenceSchema(t *testing.T) {
	schema := compileReferenceSchema(t, "agent.schema.json")
	data, err := os.ReadFile("../../testdata/minimal/agents/writer.json")
	if err != nil {
		t.Fatal(err)
	}
	validateSchemaJSON(t, schema, string(data), true)
	var base map[string]json.RawMessage
	if err := json.Unmarshal(data, &base); err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		name, value string
		valid       bool
	}{
		{"v1", `{"path":"policies/writer.json","descriptor":{"mediaType":"application/vnd.agentsuite.policy.v1+json","digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","size":123}}`, true},
		{"v2", `{"path":"policies/writer.json","descriptor":{"mediaType":"application/vnd.agentsuite.policy.v2+json","digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","size":123}}`, true},
		{"null", `null`, false},
		{"empty", `{}`, false},
		{"null descriptor", `{"path":"policies/writer.json","descriptor":null}`, false},
		{"missing size", `{"path":"policies/writer.json","descriptor":{"mediaType":"application/vnd.agentsuite.policy.v2+json","digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}`, false},
		{"other media", `{"path":"policies/writer.json","descriptor":{"mediaType":"application/json","digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","size":123}}`, false},
		{"traversal", `{"path":"policies/../writer.json","descriptor":{"mediaType":"application/vnd.agentsuite.policy.v2+json","digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","size":123}}`, false},
		{"extra field", `{"path":"policies/writer.json","other":true,"descriptor":{"mediaType":"application/vnd.agentsuite.policy.v2+json","digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","size":123}}`, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			base["policy"] = json.RawMessage(tc.value)
			value, err := json.Marshal(base)
			if err != nil {
				t.Fatal(err)
			}
			validateSchemaJSON(t, schema, string(value), tc.valid)
		})
	}
}
