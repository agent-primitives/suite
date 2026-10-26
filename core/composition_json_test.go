package core

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestCompositionRequiresAuthoredToolProviders(t *testing.T) {
	data, err := os.ReadFile("../testdata/minimal/compositions/writer-linux-amd64.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, spelling := range []string{"omitted", "null", "[]"} {
		t.Run(spelling, func(t *testing.T) {
			var fields map[string]json.RawMessage
			if err := json.Unmarshal(data, &fields); err != nil {
				t.Fatal(err)
			}
			if spelling == "omitted" {
				delete(fields, "toolProviders")
			} else {
				fields["toolProviders"] = json.RawMessage(spelling)
			}
			raw, err := json.Marshal(fields)
			if err != nil {
				t.Fatal(err)
			}
			// A reused receiver must not let its previous non-nil slice mask absence.
			value := Composition{ToolProviders: []ResolvedToolProvider{{ID: "previous"}}}
			err = Unmarshal(raw, &value)
			if spelling == "[]" {
				if err != nil || value.ToolProviders == nil || len(value.ToolProviders) != 0 {
					t.Fatalf("explicit empty array: value=%+v error=%v", value, err)
				}
			} else if err == nil || err.Error() != "toolProviders must be present and non-null" {
				t.Fatalf("%s error=%v; want authored-presence refusal", spelling, err)
			} else if len(value.ToolProviders) != 1 || value.ToolProviders[0].ID != "previous" {
				t.Fatal("failed decode changed receiver")
			}
		})
	}
	// The presence rule belongs to the child, not its manifest reference.
	reference := `{"agent":"writer","platform":{"os":"linux","architecture":"amd64"},"path":"compositions/writer-linux-amd64.json","descriptor":{"mediaType":"application/vnd.agentsuite.composition.v1+json","digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","size":1}}`
	if err := Unmarshal([]byte(reference), &CompositionRef{}); err != nil {
		t.Fatalf("CompositionRef without toolProviders: %v", err)
	}
}

func TestCompositionPreservesStrictDecoder(t *testing.T) {
	decoder := json.NewDecoder(strings.NewReader(`{"toolProviders":[],"unexpected":true}`))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&Composition{}); err == nil || !strings.Contains(err.Error(), `unknown field "unexpected"`) {
		t.Fatalf("strict composition decode=%v; want unknown-field refusal", err)
	}
}
