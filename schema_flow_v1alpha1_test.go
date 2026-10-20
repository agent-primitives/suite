package agentsuite

import (
	"encoding/json"
	"os"
	"testing"
)

func TestFlowV1Alpha1Schema(t *testing.T) {
	raw, err := os.ReadFile("testdata/flow-v1alpha1/flow.json")
	if err != nil {
		t.Fatal(err)
	}
	schema := compileReferenceSchema(t, "kmx-flow-v1alpha1.schema.json")
	validateSchemaJSON(t, schema, string(raw), true)
	for name, mutate := range map[string]func(map[string]any){
		"unknown root":       func(v map[string]any) { v["future"] = true },
		"missing edge array": func(v map[string]any) { delete(v, "edgeRequirements") },
		"null edge array":    func(v map[string]any) { v["edgeRequirements"] = nil },
		"foreign version":    func(v map[string]any) { v["schemaVersion"] = "1.0.0" },
		"third step":         func(v map[string]any) { s := v["steps"].([]any); v["steps"] = append(s, s[0]) },
		"null approval":      func(v map[string]any) { v["steps"].([]any)[1].(map[string]any)["approval"] = nil },
		"unknown input": func(v map[string]any) {
			v["steps"].([]any)[0].(map[string]any)["input"].(map[string]any)["template"] = "untrusted"
		},
		"min without runs": func(v map[string]any) { delete(v["cases"].([]any)[0].(map[string]any), "runs") },
		"null runs":        func(v map[string]any) { v["cases"].([]any)[0].(map[string]any)["runs"] = nil },
		"excessive runs":   func(v map[string]any) { v["cases"].([]any)[0].(map[string]any)["runs"] = 1001 },
		"tool assertion": func(v map[string]any) {
			v["cases"].([]any)[0].(map[string]any)["assertions"].([]any)[0].(map[string]any)["check"] = map[string]any{"id": "tool", "type": "toolCalled", "tool": "ambient"}
		},
	} {
		t.Run(name, func(t *testing.T) {
			var value map[string]any
			if err := json.Unmarshal(raw, &value); err != nil {
				t.Fatal(err)
			}
			mutate(value)
			data, err := json.Marshal(value)
			if err != nil {
				t.Fatal(err)
			}
			validateSchemaJSON(t, schema, string(data), false)
		})
	}
}
