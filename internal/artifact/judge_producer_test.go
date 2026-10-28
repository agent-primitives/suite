package artifact

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/agent-primitives/suite/judge"
)

// Storage validation accepts claims, not raw-call provenance. The producer's
// score pair must agree with the unchanged double-score policy before export.
func TestJudgeProducerEvidenceBoundary(t *testing.T) {
	threshold := 80
	definition := judge.Definition{Model: "judge", Version: "v1", Rubric: "Be correct.", MinScore: threshold}
	layout, expected, document := evidenceFixture(t, func(c *EvaluationCase) {
		c.Assertions = []EvaluationAssertion{{ID: "quality", Type: "llmJudge", Rubric: definition.Rubric, MinScore: &threshold, JudgeModel: definition.Model, JudgeVersion: definition.Version}}
	})
	digest, err := judge.ConfigurationDigest(definition)
	if err != nil {
		t.Fatal(err)
	}
	config := EvidenceJudgeConfiguration{Model: "judge", Version: "v1", Policy: EvidencePolicy{ID: EvidenceJudgePolicyID, Version: EvidenceJudgePolicyVersion, ConfigurationDigest: digest}}
	expected.Judges = []EvidenceJudgeConfiguration{config}
	load := func(name string) []byte {
		t.Helper()
		b, err := os.ReadFile(filepath.Join("../../testdata/judge-producer-v1", name))
		if err != nil {
			t.Fatal(err)
		}
		return b
	}
	request := load("request.json")
	pass, fail := load("response-pass.json"), load("response-fail.json")
	for _, tc := range []struct {
		name             string
		raw              [][]byte
		outcome, refusal string
	}{
		{"passing", [][]byte{pass, pass}, "pass", ""},
		{"below-threshold", [][]byte{fail, fail}, "fail", "policy"},
		{"split-unknown", [][]byte{pass, fail}, "unknown", "unknown"},
		{"partial-unknown", [][]byte{pass}, "unknown", "unknown"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			result, err := judge.Verify(definition, "question", "answer", request, tc.raw)
			if result.Outcome != tc.outcome || (err != nil) != (tc.name == "partial-unknown") {
				t.Fatalf("raw verification %+v %v", result, err)
			}
			for i := range document.Results {
				document.Results[i].Runs[0].Assertions[0].Judge = &EvidenceJudgeResult{Configuration: config, MinScore: threshold, Scores: append([]int{}, result.Scores...), ObservedModels: append([]string{}, result.ObservedModels...)}
			}
			evidenceCode(t, layout, expected, evidenceBytes(t, document), tc.refusal)
		})
	}
	// A fabricated but internally consistent claim can pass storage checking;
	// recomputing from genuine below-threshold raw responses cannot yield pass.
	for i := range document.Results {
		document.Results[i].Runs[0].Assertions[0].Judge = &EvidenceJudgeResult{Configuration: config, MinScore: threshold, Scores: []int{100, 100}, ObservedModels: []string{"judge", "judge"}}
	}
	evidenceCode(t, layout, expected, evidenceBytes(t, document), "")
	result, err := judge.Verify(definition, "question", "answer", request, [][]byte{fail, fail})
	if err != nil || result.Outcome != "fail" {
		t.Fatalf("forged claim passed raw verification: %+v %v", result, err)
	}
	// Independently selected accepted configuration remains authority.
	expected.Judges[0].Policy.ConfigurationDigest = digestBytes([]byte("different accepted producer"))
	evidenceCode(t, layout, expected, evidenceBytes(t, document), "policy")
}
