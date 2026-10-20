package agentsuite

import (
	"encoding/json"
	"fmt"
	"reflect"
	"strings"
	"testing"
)

const flowPayloadJSON = `{"schemaVersion":"kmx.flow/v1alpha1","id":"release","mode":"pipeline","entry":"writer","edgeRequirements":[],"steps":[{"id":"draft","member":"writer","input":{"source":"run.input"}},{"id":"review","member":"reviewer","input":{"source":"draft.output","context":"run.input"},"approval":"policy-controlled"}],"cases":[{"id":"release-facts","input":"frozen sources","assertions":[{"step":"review","check":{"id":"verdict","type":"contains","value":"Verdict: PASS"}}]}]}`

// Removing preservation of any authored field, or inventing defaults in the
// returned payload, must fail this literal round-trip contract.
func TestFlowV1Alpha1PayloadValid(t *testing.T) {
	for _, raw := range []string{
		flowPayloadJSON,
		strings.Replace(flowPayloadJSON, `"edgeRequirements":[]`, `"edgeRequirements":[{"from":"writer","to":"reviewer","approval":"required"}]`, 1),
		strings.Replace(flowPayloadJSON, `"input":"frozen sources"`, `"input":"frozen sources","runs":3,"minPasses":2`, 1),
		strings.Replace(flowPayloadJSON, `,"approval":"policy-controlled"`, ``, 1),
		strings.Replace(flowPayloadJSON, `,"context":"run.input"`, ``, 1),
		strings.Replace(flowPayloadJSON, `"source":"draft.output"`, `"source":"run.input"`, 1),
		strings.Replace(flowPayloadJSON, `"type":"contains","value":"Verdict: PASS"`, `"type":"regex","pattern":"^Verdict: PASS$","critical":false`, 1),
		strings.Replace(flowPayloadJSON, `"type":"contains"`, `"type":"notContains"`, 1),
	} {
		got, err := decodeFlowV1Alpha1([]byte(raw))
		if err != nil {
			t.Fatal(err)
		}
		encoded, err := json.Marshal(got)
		if err != nil {
			t.Fatal(err)
		}
		var wantValue, gotValue any
		if err := json.Unmarshal([]byte(raw), &wantValue); err != nil {
			t.Fatal(err)
		}
		if err := json.Unmarshal(encoded, &gotValue); err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(gotValue, wantValue) {
			t.Fatalf("payload lost or invented fields: got %s; want %s", encoded, raw)
		}
	}
}

// Omitting presence checks at any level, treating null as omission, or using
// permissive JSON decoding must cause one of these mutations to be accepted.
func TestFlowV1Alpha1PayloadStrictObjects(t *testing.T) {
	base := strings.Replace(flowPayloadJSON, `"edgeRequirements":[]`, `"edgeRequirements":[{"from":"writer","to":"reviewer","approval":"required"}]`, 1)
	for _, object := range []struct {
		path, required, optional string
	}{
		{"", "schemaVersion,id,mode,entry,edgeRequirements,steps,cases", ""},
		{"edgeRequirements/0", "from,to,approval", ""},
		{"steps/0", "id,member,input", "approval"},
		{"steps/1/input", "source", "context"},
		{"cases/0", "id,input,assertions", "runs,minPasses"},
		{"cases/0/assertions/0", "step,check", ""},
		{"cases/0/assertions/0/check", "id,type,value", "critical"},
	} {
		fields := strings.Split(object.required, ",")
		for _, field := range fields {
			for _, mutation := range []string{"missing", "null", "duplicate"} {
				t.Run(object.path+"/"+field+"/"+mutation, func(t *testing.T) {
					raw := mutateFlowPayload(t, base, object.path, func(node string) string {
						var m map[string]json.RawMessage
						if err := json.Unmarshal([]byte(node), &m); err != nil {
							t.Fatal(err)
						}
						if mutation == "duplicate" {
							return `{"` + field + `":` + string(m[field]) + `,` + node[1:]
						}
						if mutation == "missing" {
							delete(m, field)
						} else {
							m[field] = json.RawMessage(`null`)
						}
						b, err := json.Marshal(m)
						if err != nil {
							t.Fatal(err)
						}
						return string(b)
					})
					refuseFlowPayload(t, raw)
				})
			}
		}
		t.Run(object.path+"/unknown", func(t *testing.T) {
			refuseFlowPayload(t, mutateFlowPayload(t, base, object.path, func(node string) string {
				return `{"private-path":"/private/source/artifact",` + node[1:]
			}))
		})
		if object.optional != "" {
			for _, field := range strings.Split(object.optional, ",") {
				t.Run(object.path+"/"+field+"/null", func(t *testing.T) {
					refuseFlowPayload(t, mutateFlowPayload(t, base, object.path, func(node string) string {
						var m map[string]json.RawMessage
						if err := json.Unmarshal([]byte(node), &m); err != nil {
							t.Fatal(err)
						}
						m[field] = json.RawMessage(`null`)
						b, _ := json.Marshal(m)
						return string(b)
					}))
				})
			}
		}
	}
}

func TestFlowV1Alpha1PayloadSemanticRefusals(t *testing.T) {
	for _, tc := range []struct{ name, old, replacement string }{
		{"version", `kmx.flow/v1alpha1`, `1.0.0-draft`},
		{"mode", `pipeline`, `delegation`},
		{"flow id", `"id":"release"`, `"id":"Release"`},
		{"entry", `"entry":"writer"`, `"entry":"/private/source/artifact"`},
		{"member", `"member":"reviewer"`, `"member":"INVALID"`},
		{"first member", `"entry":"writer"`, `"entry":"reviewer"`},
		{"step id", `"id":"review"`, `"id":"bad/id"`},
		{"duplicate step", `"id":"review"`, `"id":"draft"`},
		{"first source", `"source":"run.input"`, `"source":"draft.output"`},
		{"forward source", `"source":"run.input"`, `"source":"review.output"`},
		{"self source", `"source":"draft.output"`, `"source":"review.output"`},
		{"unknown source", `"source":"draft.output"`, `"source":"absent.output"`},
		{"context", `"context":"run.input"`, `"context":"draft.output"`},
		{"empty context", `"context":"run.input"`, `"context":""`},
		{"approval", `policy-controlled`, `automatic`},
		{"empty approval", `policy-controlled`, ``},
		{"case id", `release-facts`, `bad/id`},
		{"empty case input", `frozen sources`, ` \t`},
		{"assertion step", `"step":"review"`, `"step":"absent"`},
		{"assertion id", `"id":"verdict"`, `"id":"bad/id"`},
		{"unknown check", `"type":"contains"`, `"type":"future","critical":false`},
		{"unsupported tool", `"type":"contains","value":"Verdict: PASS"`, `"type":"toolCalled","tool":"search"`},
		{"unsupported judge", `"type":"contains","value":"Verdict: PASS"`, `"type":"llmJudge","rubric":"quality","minScore":80,"judgeModel":"judge","judgeVersion":"1"`},
		{"inapplicable operand", `"value":"Verdict: PASS"`, `"value":"Verdict: PASS","pattern":"ok"`},
		{"empty operand", `Verdict: PASS`, ``},
		{"control operand", `Verdict: PASS`, `PASS\nFAIL`},
		{"invalid RE2", `"type":"contains","value":"Verdict: PASS"`, `"type":"regex","pattern":"(?=PASS)"`},
		{"long regex", `"type":"contains","value":"Verdict: PASS"`, `"type":"regex","pattern":"` + strings.Repeat("a", 1025) + `"`},
		{"runs zero", `"input":"frozen sources"`, `"input":"frozen sources","runs":0`},
		{"runs negative", `"input":"frozen sources"`, `"input":"frozen sources","runs":-1`},
		{"runs fraction", `"input":"frozen sources"`, `"input":"frozen sources","runs":1.5`},
		{"runs limit", `"input":"frozen sources"`, `"input":"frozen sources","runs":1001`},
		{"minPasses needs runs", `"input":"frozen sources"`, `"input":"frozen sources","minPasses":1`},
		{"minPasses zero", `"input":"frozen sources"`, `"input":"frozen sources","runs":2,"minPasses":0`},
		{"minPasses exceeds runs", `"input":"frozen sources"`, `"input":"frozen sources","runs":2,"minPasses":3`},
	} {
		t.Run(tc.name, func(t *testing.T) {
			if !strings.Contains(flowPayloadJSON, tc.old) {
				t.Fatal("mutation did not match fixture")
			}
			refuseFlowPayload(t, strings.Replace(flowPayloadJSON, tc.old, tc.replacement, 1))
		})
	}
	for _, edge := range []string{
		`{"from":"INVALID","to":"reviewer","approval":"required"}`,
		`{"from":"writer","to":"bad/id","approval":"required"}`,
		`{"from":"writer","to":"reviewer","approval":"automatic"}`,
		`{"from":"writer","to":"reviewer","approval":"required"},{"from":"writer","to":"reviewer","approval":"policy-controlled"}`,
	} {
		refuseFlowPayload(t, strings.Replace(flowPayloadJSON, `"edgeRequirements":[]`, `"edgeRequirements":[`+edge+`]`, 1))
	}
	for _, path := range []string{"steps", "cases", "cases/0/assertions"} {
		refuseFlowPayload(t, mutateFlowPayload(t, flowPayloadJSON, path, func(string) string { return `[]` }))
		refuseFlowPayload(t, mutateFlowPayload(t, flowPayloadJSON, path, func(node string) string {
			return node[:len(node)-1] + "," + node[1:]
		}))
	}
}

func TestFlowV1Alpha1PayloadBudgets(t *testing.T) {
	for _, tc := range []struct {
		name                    string
		cases, runs, assertions int
		valid                   bool
	}{
		{"case boundary", 128, 1, 1, true}, {"case overflow", 129, 1, 1, false},
		{"run boundary", 1, 1000, 1, true},
		{"total runs boundary", 8, 512, 1, true}, {"total runs overflow", 7, 586, 1, false},
		{"assertion boundary", 1, 1, 1000, true}, {"assertion overflow", 1, 1, 1001, false},
		{"row boundary", 1, 1000, 32, true}, {"row overflow", 1, 1000, 33, false},
		{"rows across cases", 2, 1000, 17, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			var cases []string
			for c := 0; c < tc.cases; c++ {
				var assertions []string
				for a := 0; a < tc.assertions; a++ {
					assertions = append(assertions, fmt.Sprintf(`{"step":"review","check":{"id":"a%d","type":"contains","value":"PASS"}}`, a))
				}
				cases = append(cases, fmt.Sprintf(`{"id":"case%d","input":"sources","runs":%d,"assertions":[%s]}`, c, tc.runs, strings.Join(assertions, ",")))
			}
			raw := mutateFlowPayload(t, flowPayloadJSON, "cases", func(string) string { return "[" + strings.Join(cases, ",") + "]" })
			_, err := decodeFlowV1Alpha1([]byte(raw))
			if (err == nil) != tc.valid {
				t.Fatalf("valid=%v: %v", tc.valid, err)
			}
		})
	}
}

func TestFlowV1Alpha1PayloadJSONBounds(t *testing.T) {
	for _, raw := range []string{
		`null`, `[]`, flowPayloadJSON + `{}`, flowPayloadJSON + strings.Repeat(" ", maxJSONBytes),
		strings.Replace(flowPayloadJSON, `frozen sources`, string([]byte{0xff}), 1),
		strings.Replace(flowPayloadJSON, `frozen sources`, `\ud800`, 1),
		strings.Replace(flowPayloadJSON, `"cases":`, `"Cases":`, 1),
		strings.Repeat("[", maxJSONDepth+1) + strings.Repeat("]", maxJSONDepth+1),
	} {
		refuseFlowPayload(t, raw)
	}
}

func refuseFlowPayload(t *testing.T, raw string) {
	t.Helper()
	got, err := decodeFlowV1Alpha1([]byte(raw))
	if err == nil {
		t.Fatal("invalid flow was accepted")
	}
	if !reflect.DeepEqual(got, FlowV1Alpha1{}) {
		t.Fatal("invalid flow returned a partial payload")
	}
	if strings.Contains(err.Error(), "private-path") || strings.Contains(err.Error(), "/private/source/artifact") {
		t.Fatalf("error leaked input: %v", err)
	}
}

// Only fixture navigation is shared; mutations and acceptance expectations are
// independent of the production decoder and validators.
func mutateFlowPayload(t *testing.T, raw, path string, change func(string) string) string {
	t.Helper()
	if path == "" {
		return change(raw)
	}
	part, rest, _ := strings.Cut(path, "/")
	var encoded []byte
	var err error
	if strings.HasPrefix(raw, "[") {
		var items []json.RawMessage
		if err := json.Unmarshal([]byte(raw), &items); err != nil {
			t.Fatal(err)
		}
		var i int
		if _, err := fmt.Sscanf(part, "%d", &i); err != nil {
			t.Fatal(err)
		}
		items[i] = json.RawMessage(mutateFlowPayload(t, string(items[i]), rest, change))
		encoded, err = json.Marshal(items)
	} else {
		var fields map[string]json.RawMessage
		if err := json.Unmarshal([]byte(raw), &fields); err != nil {
			t.Fatal(err)
		}
		fields[part] = json.RawMessage(mutateFlowPayload(t, string(fields[part]), rest, change))
		encoded, err = json.Marshal(fields)
	}
	if err != nil {
		t.Fatal(err)
	}
	return string(encoded)
}
