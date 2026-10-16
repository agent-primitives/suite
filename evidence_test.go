package agentsuite

import (
	"bytes"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// A real packaged public evaluation, with identity derived from fixture helpers,
// not a hand-maintained manifest or case hash.
func evidenceFixture(t *testing.T, mutate func(*EvaluationCase)) (string, ExpectedEvaluation, EvaluationEvidence) {
	t.Helper()
	root, indexRef := writeEvaluationSuite(t, func(root string, index *EvaluationIndex) {
		if mutate == nil {
			return
		}
		for i, ref := range index.Cases {
			var c EvaluationCase
			data, err := os.ReadFile(filepath.Join(root, ref.Path))
			if err != nil {
				t.Fatal(err)
			}
			if err := Unmarshal(data, &c); err != nil {
				t.Fatal(err)
			}
			mutate(&c)
			index.Cases[i].Descriptor = mustWriteJSON(t, root, ref.Path, MediaTypeEvaluationCase, c)
		}
	})
	layout := writeTestOCILayout(t, root)
	content, err := loadOCILayoutContent(layout)
	if err != nil {
		t.Fatal(err)
	}
	v, _, err := validateContentGraph(content)
	if err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(filepath.Join(layout, "index.json"))
	if err != nil {
		t.Fatal(err)
	}
	var index ociIndex
	if err := Unmarshal(raw, &index); err != nil {
		t.Fatal(err)
	}
	manifest := index.Manifests[0]
	desc := func(d Descriptor) EvidenceDescriptor { return EvidenceDescriptor{d.MediaType, d.Digest, d.Size} }
	digest := digestBytes([]byte("public non-secret configuration"))
	identity := EvidenceImplementation{ID: "example", Version: "1.0.0", Digest: digest}
	policy := EvidencePolicy{ID: EvidencePolicyID, Version: EvidencePolicyVersion, ConfigurationDigest: digest}
	e := EvaluationEvidence{
		SchemaVersion: EvidenceSchemaVersion, MediaType: MediaTypeEvaluationEvidence,
		Subject:    EvidenceSubject{Manifest: EvidenceDescriptor{manifest.MediaType, manifest.Digest, manifest.Size}, MemberID: "writer", MemberDigest: v.suite.Agents[0].Descriptor.Digest, CompositionDigest: v.suite.Compositions[0].Descriptor.Digest, BuildProfileDigest: v.suite.BuildProfiles[0].Descriptor.Digest, Platform: EvidencePlatform{OS: "linux", Architecture: "amd64", Variant: ""}},
		Execution:  EvidenceExecution{Runtime: identity, Model: EvidenceModel{Protocol: "openai-compatible", ID: "example-model", ConfigurationDigest: digest}, Harness: identity, Renderer: identity, Profile: identity, ConfigurationDigest: digest},
		Evaluator:  EvidenceEvaluator{Identity: EvidenceEvaluatorIdentity{ID: "example", Version: "1.0.0", Policy: policy}, StartedAt: "2026-01-01T00:00:00Z", CompletedAt: "2026-01-01T00:01:00Z"},
		Evaluation: EvidenceEvaluation{Index: EvidenceFileRef{Path: indexRef.Path, Descriptor: desc(indexRef.Descriptor)}},
	}
	var publicIndex EvaluationIndex
	data, _ := content.data(indexRef.Path)
	if err := Unmarshal(data, &publicIndex); err != nil {
		t.Fatal(err)
	}
	for _, ref := range publicIndex.Cases {
		var c EvaluationCase
		data, _ := content.data(ref.Path)
		if err := Unmarshal(data, &c); err != nil {
			t.Fatal(err)
		}
		runs, min := 1, 1
		if c.Runs != nil {
			runs = *c.Runs
			min = runs
		}
		if c.MinPasses != nil {
			min = *c.MinPasses
		}
		e.Evaluation.Cases = append(e.Evaluation.Cases, EvidenceCaseRef{ID: c.ID, Path: ref.Path, Descriptor: desc(ref.Descriptor), Runs: runs, MinPasses: min})
		row := EvidenceCaseResult{ID: c.ID, Outcome: "pass"}
		for n := 1; n <= runs; n++ {
			run := EvidenceRunResult{Number: n, Status: "completed", Outcome: "pass"}
			for _, a := range c.Assertions {
				run.Assertions = append(run.Assertions, EvidenceAssertionResult{ID: a.ID, Type: a.Type, Outcome: "pass"})
			}
			row.Runs = append(row.Runs, run)
		}
		e.Results = append(e.Results, row)
	}
	expected := ExpectedEvaluation{Subject: e.Subject, Execution: e.Execution, Evaluator: e.Evaluator.Identity}
	return layout, expected, e
}

func evidenceBytes(t *testing.T, e EvaluationEvidence) []byte {
	t.Helper()
	b, err := json.Marshal(e)
	if err != nil {
		t.Fatal(err)
	}
	return b
}
func evidenceCode(t *testing.T, layout string, expected ExpectedEvaluation, data []byte, code string) {
	t.Helper()
	got, err := VerifyEvaluation(layout, expected, bytes.NewReader(data))
	if code == "" {
		if err != nil || got == nil {
			t.Fatalf("verification failed: %v", err)
		}
		return
	}
	var refusal *EvidenceRefusal
	if got != nil || !errors.As(err, &refusal) || refusal.Code != code {
		t.Fatalf("got summary=%+v error=%v; want %s", got, err, code)
	}
}

func TestEvidenceOfflineSuccess(t *testing.T) {
	layout, expected, e := evidenceFixture(t, nil)
	got, err := VerifyEvaluation(layout, expected, bytes.NewReader(evidenceBytes(t, e)))
	if err != nil {
		t.Fatal(err)
	}
	if got.Subject != expected.Subject || got.Cases != 2 || got.Runs != 2 || got.CompletedAt != "2026-01-01T00:01:00Z" || !got.Unsigned {
		t.Fatalf("unexpected verified summary: %+v", got)
	}
}

func TestEvidenceIdentityAndCoverage(t *testing.T) {
	tests := []struct {
		name, code string
		mutate     func(*EvaluationEvidence)
	}{
		{"manifest-digest", "subject", func(e *EvaluationEvidence) { e.Subject.Manifest.Digest = digestBytes([]byte("wrong")) }},
		{"manifest-size", "subject", func(e *EvaluationEvidence) { e.Subject.Manifest.Size++ }},
		{"member", "subject", func(e *EvaluationEvidence) { e.Subject.MemberID = "other" }},
		{"member-digest", "subject", func(e *EvaluationEvidence) { e.Subject.MemberDigest = digestBytes(nil) }},
		{"composition", "subject", func(e *EvaluationEvidence) { e.Subject.CompositionDigest = digestBytes(nil) }},
		{"build", "subject", func(e *EvaluationEvidence) { e.Subject.BuildProfileDigest = digestBytes(nil) }},
		{"platform", "subject", func(e *EvaluationEvidence) { e.Subject.Platform.Architecture = "arm64" }},
		{"runtime", "subject", func(e *EvaluationEvidence) { e.Execution.Runtime.Version = "2.0.0" }},
		{"runtime-implementation", "subject", func(e *EvaluationEvidence) { e.Execution.Runtime.Digest = digestBytes(nil) }},
		{"model", "subject", func(e *EvaluationEvidence) { e.Execution.Model.ID = "other" }},
		{"model-config", "subject", func(e *EvaluationEvidence) { e.Execution.Model.ConfigurationDigest = digestBytes(nil) }},
		{"harness", "subject", func(e *EvaluationEvidence) { e.Execution.Harness.ID = "other" }},
		{"renderer", "subject", func(e *EvaluationEvidence) { e.Execution.Renderer.Digest = digestBytes(nil) }},
		{"profile", "subject", func(e *EvaluationEvidence) { e.Execution.Profile.Digest = digestBytes(nil) }},
		{"execution-config", "subject", func(e *EvaluationEvidence) { e.Execution.ConfigurationDigest = digestBytes(nil) }},
		{"evaluator", "policy", func(e *EvaluationEvidence) { e.Evaluator.Identity.Version = "2.0.0" }},
		{"policy", "unsupported", func(e *EvaluationEvidence) { e.Evaluator.Identity.Policy.ID = "future-counts" }},
		{"policy-version", "unsupported", func(e *EvaluationEvidence) { e.Evaluator.Identity.Policy.Version = "2.0.0" }},
		{"policy-config", "policy", func(e *EvaluationEvidence) { e.Evaluator.Identity.Policy.ConfigurationDigest = digestBytes(nil) }},
		{"index", "coverage", func(e *EvaluationEvidence) { e.Evaluation.Index.Descriptor.Digest = digestBytes(nil) }},
		{"case-digest", "coverage", func(e *EvaluationEvidence) { e.Evaluation.Cases[0].Descriptor.Digest = digestBytes(nil) }},
		{"reorder", "coverage", func(e *EvaluationEvidence) {
			e.Evaluation.Cases[0], e.Evaluation.Cases[1] = e.Evaluation.Cases[1], e.Evaluation.Cases[0]
		}},
		{"missing-case", "coverage", func(e *EvaluationEvidence) { e.Results = e.Results[:1] }},
		{"extra-case", "coverage", func(e *EvaluationEvidence) { e.Results = append(e.Results, e.Results[0]) }},
		{"duplicate-case", "coverage", func(e *EvaluationEvidence) { e.Results[1] = e.Results[0] }},
		{"missing-run", "coverage", func(e *EvaluationEvidence) { e.Results[0].Runs = []EvidenceRunResult{} }},
		{"run-number", "coverage", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Number = 2 }},
		{"missing-assertion", "coverage", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions = e.Results[0].Runs[0].Assertions[:1] }},
		{"duplicate-assertion", "coverage", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[1] = e.Results[0].Runs[0].Assertions[0] }},
		{"unknown", "unknown", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Outcome = "unknown" }},
		{"false-pass", "policy", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Outcome = "fail" }},
		{"false-case-pass", "policy", func(e *EvaluationEvidence) { e.Results[0].Outcome = "fail" }},
		{"reversed-time", "malformed", func(e *EvaluationEvidence) { e.Evaluator.StartedAt = "2026-01-02T00:00:00Z" }},
		{"non-utc", "malformed", func(e *EvaluationEvidence) { e.Evaluator.StartedAt = "2026-01-01T00:00:00+00:00" }},
		{"time-invalid", "malformed", func(e *EvaluationEvidence) { e.Evaluator.StartedAt = "yesterday" }},
		{"unsafe-id", "malformed", func(e *EvaluationEvidence) { e.Execution.Model.ID = "https://canary.invalid/secret" }},
		{"credential", "malformed", func(e *EvaluationEvidence) { e.Execution.Model.ID = "sk-canary-secret" }},
		{"endpoint", "malformed", func(e *EvaluationEvidence) { e.Execution.Runtime.ID = "api.canary.invalid" }},
	}
	layout, expected, original := evidenceFixture(t, nil)
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var e EvaluationEvidence
			if err := json.Unmarshal(evidenceBytes(t, original), &e); err != nil {
				t.Fatal(err)
			}
			tt.mutate(&e)
			evidenceCode(t, layout, expected, evidenceBytes(t, e), tt.code)
		})
	}
	t.Run("empty-expectations", func(t *testing.T) {
		evidenceCode(t, layout, ExpectedEvaluation{}, evidenceBytes(t, original), "missing")
	})
	t.Run("loose-content", func(t *testing.T) {
		root, _ := writeEvaluationSuite(t, nil)
		evidenceCode(t, root, expected, evidenceBytes(t, original), "artifact")
	})
	t.Run("self-consistent-wrong-subject", func(t *testing.T) {
		e := original
		e.Subject.Manifest.Size++
		expected.Subject = e.Subject
		evidenceCode(t, layout, expected, evidenceBytes(t, e), "subject")
	})
}

func TestEvidenceThresholdAndUnknownVeto(t *testing.T) {
	two, one := 2, 1
	layout, expected, e := evidenceFixture(t, func(c *EvaluationCase) {
		c.Runs = &two
		c.MinPasses = &one
		for i := range c.Assertions {
			v := false
			c.Assertions[i].Critical = &v
		}
	})
	for i := range e.Results {
		e.Results[i].Runs[0].Outcome = "fail"
		for j := range e.Results[i].Runs[0].Assertions {
			e.Results[i].Runs[0].Assertions[j].Outcome = "fail"
		}
	}
	evidenceCode(t, layout, expected, evidenceBytes(t, e), "")
	t.Run("omitted-failed-repeat", func(t *testing.T) {
		var copy EvaluationEvidence
		if err := json.Unmarshal(evidenceBytes(t, e), &copy); err != nil {
			t.Fatal(err)
		}
		copy.Results[0].Runs = copy.Results[0].Runs[1:]
		evidenceCode(t, layout, expected, evidenceBytes(t, copy), "coverage")
	})
	for _, status := range []string{"error", "cancelled", "unknown"} {
		t.Run(status+"-spare-run", func(t *testing.T) {
			var copy EvaluationEvidence
			_ = json.Unmarshal(evidenceBytes(t, e), &copy)
			copy.Results[0].Runs[0].Status = status
			evidenceCode(t, layout, expected, evidenceBytes(t, copy), "unknown")
		})
	}
	t.Run("unknown-spare-run", func(t *testing.T) {
		var copy EvaluationEvidence
		_ = json.Unmarshal(evidenceBytes(t, e), &copy)
		copy.Results[0].Runs[0].Assertions[0].Outcome = "unknown"
		evidenceCode(t, layout, expected, evidenceBytes(t, copy), "unknown")
	})
	for i := range e.Results {
		e.Results[i].Outcome = "fail"
		e.Results[i].Runs[1].Outcome = "fail"
		for j := range e.Results[i].Runs[1].Assertions {
			e.Results[i].Runs[1].Assertions[j].Outcome = "fail"
		}
	}
	evidenceCode(t, layout, expected, evidenceBytes(t, e), "not-passing")
}

func TestEvidenceUnsupportedAssertionsAndLimits(t *testing.T) {
	for _, typ := range []string{"toolCalled", "future-count"} {
		t.Run(typ, func(t *testing.T) {
			layout, expected, e := evidenceFixture(t, func(c *EvaluationCase) {
				v := false
				a := EvaluationAssertion{ID: "observation", Type: typ, Critical: &v}
				if typ == "toolCalled" {
					a.Tool = "tool"
				} else {
					a.Value = "public operand"
				}
				c.Assertions = []EvaluationAssertion{a}
			})
			code := "unsupported"
			if typ == "future-count" {
				code = "unknown"
			}
			evidenceCode(t, layout, expected, evidenceBytes(t, e), code)
		})
	}
	runs := 1001
	layout, expected, e := evidenceFixture(t, func(c *EvaluationCase) { c.Runs = &runs })
	evidenceCode(t, layout, expected, evidenceBytes(t, e), "limit")
}

func TestEvidenceJudgeDoubleScore(t *testing.T) {
	threshold := 50
	layout, expected, e := evidenceFixture(t, func(c *EvaluationCase) {
		c.Assertions = []EvaluationAssertion{{ID: "quality", Type: "llmJudge", Rubric: "PRIVATE_RUBRIC_CANARY", MinScore: &threshold, JudgeModel: "judge", JudgeVersion: "v1"}}
	})
	config := EvidenceJudgeConfiguration{Model: "judge", Version: "v1", Policy: EvidencePolicy{ID: EvidenceJudgePolicyID, Version: EvidenceJudgePolicyVersion, ConfigurationDigest: digestBytes([]byte("non-secret judge configuration"))}}
	expected.Judges = []EvidenceJudgeConfiguration{config}
	for i := range e.Results {
		e.Results[i].Runs[0].Assertions[0].Judge = &EvidenceJudgeResult{Configuration: config, ObservedModels: []string{"judge", "judge-v1"}, MinScore: 50, Scores: []int{50, 100}}
	}
	evidenceCode(t, layout, expected, evidenceBytes(t, e), "")
	for _, tt := range []struct {
		name, code string
		mutate     func(*EvaluationEvidence)
	}{
		{"split", "unknown", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Judge.Scores = []int{49, 50} }},
		{"scores-disagree", "policy", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Judge.Scores = []int{0, 49} }},
		{"threshold", "policy", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Judge.MinScore = 51 }},
		{"model", "policy", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Judge.Configuration.Model = "other" }},
		{"version", "policy", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Judge.Configuration.Version = "v2" }},
		{"config", "policy", func(e *EvaluationEvidence) {
			e.Results[0].Runs[0].Assertions[0].Judge.Configuration.Policy.ConfigurationDigest = digestBytes(nil)
		}},
		{"policy", "unsupported", func(e *EvaluationEvidence) {
			e.Results[0].Runs[0].Assertions[0].Judge.Configuration.Policy.ID = "split-pass"
		}},
		{"unavailable", "unknown", func(e *EvaluationEvidence) {
			e.Results[0].Runs[0].Assertions[0].Judge.Scores = []int{}
			e.Results[0].Runs[0].Assertions[0].Judge.ObservedModels = []string{}
		}},
		{"observed-model", "policy", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Judge.ObservedModels[0] = "wrong" }},
		{"missing-judge", "coverage", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Judge = nil }},
		{"out-of-range", "malformed", func(e *EvaluationEvidence) { e.Results[0].Runs[0].Assertions[0].Judge.Scores = []int{101, 100} }},
	} {
		t.Run(tt.name, func(t *testing.T) {
			var copy EvaluationEvidence
			_ = json.Unmarshal(evidenceBytes(t, e), &copy)
			tt.mutate(&copy)
			evidenceCode(t, layout, expected, evidenceBytes(t, copy), tt.code)
		})
	}
	expected.Judges = nil
	evidenceCode(t, layout, expected, evidenceBytes(t, e), "policy")
}

type evidenceErrorReader struct{}

func (evidenceErrorReader) Read([]byte) (int, error) { return 0, errors.New("PRIVATE_READER_CANARY") }

func TestEvidencePrivacyAndBoundedRead(t *testing.T) {
	layout, expected, e := evidenceFixture(t, func(c *EvaluationCase) {
		c.Input = "PRIVATE_INPUT_CANARY"
		for i := range c.Assertions {
			if c.Assertions[i].Type != "regex" {
				c.Assertions[i].Value = "PRIVATE_OPERAND_CANARY"
			}
		}
	})
	summary, err := VerifyEvaluation(layout, expected, bytes.NewReader(evidenceBytes(t, e)))
	if err != nil {
		t.Fatal(err)
	}
	b, _ := json.Marshal(summary)
	if strings.Contains(string(b), "PRIVATE_") || strings.Contains(string(evidenceBytes(t, e)), "PRIVATE_") {
		t.Fatal("payload leaked")
	}
	for _, reader := range []io.Reader{nil, evidenceErrorReader{}, strings.NewReader(`{"PRIVATE_JSON_CANARY":null}`)} {
		got, err := VerifyEvaluation("PRIVATE_PATH_CANARY", expected, reader)
		if got != nil || err == nil || strings.Contains(err.Error(), "PRIVATE_") {
			t.Fatalf("unsafe error: %v", err)
		}
	}
	data := append(evidenceBytes(t, e), bytes.Repeat([]byte(" "), maxJSONBytes)...)
	reader := bytes.NewReader(data)
	_, err = VerifyEvaluation(layout, expected, reader)
	var refusal *EvidenceRefusal
	if !errors.As(err, &refusal) || refusal.Code != "limit" || reader.Len() != len(data)-(maxJSONBytes+1) {
		t.Fatalf("read was not strictly bounded: remaining=%d err=%v", reader.Len(), err)
	}
	// Exported error values cannot turn an attacker-controlled Code into diagnostics.
	if strings.Contains((&EvidenceRefusal{Code: "PRIVATE_CODE_CANARY"}).Error(), "PRIVATE_") {
		t.Fatal("unsafe custom refusal code")
	}
}
