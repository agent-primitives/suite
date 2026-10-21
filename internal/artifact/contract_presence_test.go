package artifact

import (
	"encoding/json"
	"os"
	"testing"
)

func TestModelRequirementSchemaAndDecoderPresence(t *testing.T) {
	fixture, err := os.ReadFile("../../testdata/minimal/agents/writer.json")
	if err != nil {
		t.Fatal(err)
	}
	var document map[string]json.RawMessage
	if err := json.Unmarshal(fixture, &document); err != nil {
		t.Fatal(err)
	}
	schema := compileReferenceSchema(t, "agent.schema.json")
	capabilities := `"capabilities":{"api":"openai-chat-completions-v1","contextTokens":8192,"outputTokens":1024,"streaming":false,"toolCalling":false}`
	for _, tc := range []struct {
		name, fields string
		valid        bool
	}{
		{"exact model", `"model":"example"`, true},
		{"capability model", capabilities, true},
		{"neither selection", ``, false},
		{"both selections", `"model":"example",` + capabilities, false},
		{"exact model null capabilities", `"model":"example","capabilities":null`, false},
		{"null capabilities alone", `"capabilities":null`, false},
		{"capabilities empty model", capabilities + `,"model":""`, false},
		{"capabilities null model", capabilities + `,"model":null`, false},
		{"capabilities empty endpoint", capabilities + `,"endpointEnv":""`, false},
		{"capabilities null endpoint", capabilities + `,"endpointEnv":null`, false},
		{"capabilities bound endpoint", capabilities + `,"endpointEnv":"MODEL_URL"`, false},
		{"capabilities empty secrets", capabilities + `,"secretRefs":[]`, false},
		{"capabilities null secrets", capabilities + `,"secretRefs":null`, false},
		{"capabilities bound secrets", capabilities + `,"secretRefs":["model-key"]`, false},
		{"exact model empty secrets", `"model":"example","secretRefs":[]`, true},
		{"exact model bindings", `"model":"example","endpointEnv":"MODEL_URL","secretRefs":["model-key"]`, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			model := `{"protocol":"openai-compatible"`
			if tc.fields != "" {
				model += "," + tc.fields
			}
			document["model"] = json.RawMessage(model + "}")
			raw, err := json.Marshal(document)
			if err != nil {
				t.Fatal(err)
			}
			validateSchemaJSON(t, schema, string(raw), tc.valid)
			var agent Agent
			err = Unmarshal(raw, &agent)
			if err == nil {
				err = validateAgent(agent)
			}
			if (err == nil) != tc.valid {
				t.Fatalf("decoder/semantic parity: %v", err)
			}
		})
	}
}

func TestBuildProfileExecutionSchemaAndDecoderPresence(t *testing.T) {
	fixture, err := os.ReadFile("../../testdata/minimal/build-profiles/default.json")
	if err != nil {
		t.Fatal(err)
	}
	var document map[string]json.RawMessage
	if err := json.Unmarshal(fixture, &document); err != nil {
		t.Fatal(err)
	}
	schema := compileReferenceSchema(t, "build-profile.schema.json")
	for _, tc := range []struct {
		name, execution string
		valid           bool
	}{
		{"omitted", "", true},
		{"null", `null`, false},
		{"empty object", `{}`, false},
		{"contract", `{"kind":"http-v1","protocol":"openai-chat-v1","port":8080,"healthPath":"/healthz","inputs":[]}`, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			delete(document, "execution")
			if tc.execution != "" {
				document["execution"] = json.RawMessage(tc.execution)
			}
			raw, err := json.Marshal(document)
			if err != nil {
				t.Fatal(err)
			}
			validateSchemaJSON(t, schema, string(raw), tc.valid)
			var profile BuildProfile
			err = Unmarshal(raw, &profile)
			if err == nil {
				err = validateBuildProfile(profile)
			}
			if (err == nil) != tc.valid {
				t.Fatalf("decoder/semantic parity: %v", err)
			}
		})
	}
}
