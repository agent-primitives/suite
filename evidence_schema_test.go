package agentsuite

import (
	"encoding/json"
	"strings"
	"testing"
)

// Removing any required field (including zero-valued fields) or accepting a
// null/extension anywhere is a wire-contract bug in either implementation.
func TestEvidenceSchemaParity(t *testing.T) {
	_, _, e := evidenceFixture(t, nil)
	schema := compileReferenceSchema(t, "eval-evidence.schema.json")
	original := evidenceBytes(t, e)
	check := func(t *testing.T, data []byte, valid bool) {
		t.Helper()
		validateSchemaJSON(t, schema, string(data), valid)
		var got EvaluationEvidence
		err := Unmarshal(data, &got)
		if (err == nil) != valid {
			t.Fatalf("Go/schema disagreement valid=%v error=%v document=%s", valid, err, data)
		}
	}
	check(t, original, true)
	var value any
	if err := json.Unmarshal(original, &value); err != nil {
		t.Fatal(err)
	}
	var walk func(any, string)
	walk = func(v any, path string) {
		switch object := v.(type) {
		case map[string]any:
			for k, child := range object {
				delete(object, k)
				b, _ := json.Marshal(value)
				check(t, b, false)
				object[k] = nil
				b, _ = json.Marshal(value)
				check(t, b, false)
				object[k] = child
				walk(child, path+"/"+k)
			}
			object["unexpected"] = "PRIVATE_CANARY"
			b, _ := json.Marshal(value)
			check(t, b, false)
			delete(object, "unexpected")
		case []any:
			for _, child := range object {
				walk(child, path+"/item")
			}
		}
	}
	walk(value, "")
	for _, tt := range []struct {
		old, new string
		valid    bool
	}{
		{`"schemaVersion":"1.0.0"`, `"schemaVersion":"2.0.0"`, false},
		{`"size":`, `"size":null,"ignored":`, false},
		{`"outcome":"pass"`, `"outcome":"unknown"`, true},
		{`"outcome":"pass"`, `"outcome":"error"`, false},
		{`"status":"completed"`, `"status":"cancelled"`, true},
		{`"variant":""`, `"variant":"v8"`, true},
		{`"id":"example-model"`, `"id":"https://canary.invalid"`, false},
		{`"id":"example-model"`, `"id":"sk-canary"`, false},
		{`"id":"example-model"`, `"id":"api.canary.invalid"`, false},
		{`"startedAt":"2026-01-01T00:00:00Z"`, `"startedAt":"2026-01-01T00:00:00,5Z"`, false},
		{`"startedAt":"2026-01-01T00:00:00Z"`, `"startedAt":"2026-01-01T0:00:00Z"`, false},
		{`"startedAt":"2026-01-01T00:00:00Z"`, `"startedAt":"2026-01-01T00:00:00.1234567890Z"`, false},
		{`"startedAt":"2026-01-01T00:00:00Z"`, `"startedAt":"2026-01-01T00:00:00.5Z"`, true},
		{`evals/writer/index.json`, `evals/api.canary.invalid/index.json`, false},
		{`evals/writer/index.json`, `evals/sk-canary/index.json`, false},
		{`evals/writer/cases/capital.json`, `evals/writer/cases/api.canary.invalid.json`, false},
		{`evals/writer/cases/capital.json`, `evals/writer/cases/sk-canary.json`, false},
		{`evals/writer/cases/capital.json`, `evals/writer/cases/capital.v1.json`, true},
		{`"minPasses":1`, `"minPasses":0`, false},
		{`"runs":1`, `"runs":1001`, false},
	} {
		data := []byte(strings.Replace(string(original), tt.old, tt.new, 1))
		if string(data) == string(original) {
			t.Fatalf("mutation not applied: %s", tt.old)
		}
		check(t, data, tt.valid)
	}
}

func TestEvidenceStrictJSON(t *testing.T) {
	layout, expected, e := evidenceFixture(t, nil)
	original := evidenceBytes(t, e)
	for _, data := range [][]byte{
		nil, []byte("null"), []byte(`{}`), append(append([]byte{}, original...), []byte(` {}`)...),
		[]byte(strings.Replace(string(original), `"schemaVersion":`, `"schemaVersion":"1.0.0","schemaVersion":`, 1)),
		[]byte(strings.Replace(string(original), `"schemaVersion":`, `"SchemaVersion":`, 1)),
		[]byte(strings.Replace(string(original), `"minPasses":1`, `"minPasses":1.0`, 1)),
	} {
		got, err := VerifyEvaluation(layout, expected, strings.NewReader(string(data)))
		if got != nil || err == nil {
			t.Fatalf("invalid JSON accepted: %s", data)
		}
	}
}

func TestEvidenceJudgeSchemaParity(t *testing.T) {
	_, _, e := evidenceFixture(t, nil)
	config := EvidenceJudgeConfiguration{Model: "judge", Version: "v1", Policy: EvidencePolicy{ID: EvidenceJudgePolicyID, Version: EvidenceJudgePolicyVersion, ConfigurationDigest: digestBytes(nil)}}
	row := &e.Results[0].Runs[0].Assertions[0]
	row.Type = "llmJudge"
	row.Judge = &EvidenceJudgeResult{Configuration: config, ObservedModels: []string{"judge", "judge-v1"}, Scores: []int{0, 100}, MinScore: 0}
	schema := compileReferenceSchema(t, "eval-evidence.schema.json")
	original := evidenceBytes(t, e)
	validateSchemaJSON(t, schema, string(original), true)
	// Required zero score, score cardinality, and judge-only field application.
	for _, replace := range [][2]string{{`,"minScore":0`, ``}, {`"scores":[0,100]`, `"scores":[null,100]`}, {`"scores":[0,100]`, `"scores":[0]`}, {`"scores":[0,100]`, `"scores":[0,101]`}, {`"observedModels":["judge","judge-v1"]`, `"observedModels":null`}, {`"type":"llmJudge"`, `"type":"contains"`}} {
		data := strings.Replace(string(original), replace[0], replace[1], 1)
		if data == string(original) {
			t.Fatal("mutation not applied")
		}
		validateSchemaJSON(t, schema, data, false)
		var got EvaluationEvidence
		if err := Unmarshal([]byte(data), &got); err == nil {
			t.Fatalf("invalid judge shape accepted: %s", data)
		}
	}
}
