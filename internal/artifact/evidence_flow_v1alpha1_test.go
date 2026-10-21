package artifact

import (
	"bytes"
	"errors"
	"path/filepath"
	"testing"
)

func flowEvidenceFixture(t *testing.T) (string, ExpectedEvaluation, EvaluationEvidence) {
	t.Helper()
	_, expected, e := evidenceFixture(t, nil)
	layout := writeTestOCILayout(t, writeFlowSuite(t))
	var index ociIndex
	readStrictJSON(t, filepath.Join(layout, "index.json"), &index)
	d := index.Manifests[0]
	expected.Subject.Manifest = EvidenceDescriptor{MediaType: d.MediaType, Digest: d.Digest, Size: d.Size}
	e.Subject.Manifest = expected.Subject.Manifest
	// Independently selected non-secret execution configuration includes exact B.
	expected.Execution.ConfigurationDigest = digestBytes([]byte("destination-binding-A"))
	e.Execution.ConfigurationDigest = expected.Execution.ConfigurationDigest
	return layout, expected, e
}

func TestFlowV1Alpha1EvidenceOriginalSubject(t *testing.T) {
	layout, expected, e := flowEvidenceFixture(t)
	raw := evidenceBytes(t, e)
	got, err := VerifyEvaluationFlowV1Alpha1(layout, expected, bytes.NewReader(raw))
	if err != nil || got == nil || got.Subject.Manifest != expected.Subject.Manifest {
		t.Fatalf("original flow subject not verified: %v", err)
	}
	evidenceCode(t, layout, expected, raw, "artifact")
	for name, mutate := range map[string]func(*ExpectedEvaluation, *EvaluationEvidence){
		"destination configuration": func(x *ExpectedEvaluation, _ *EvaluationEvidence) {
			x.Execution.ConfigurationDigest = digestBytes([]byte("destination-binding-B"))
		},
		"member digest": func(_ *ExpectedEvaluation, e *EvaluationEvidence) {
			e.Subject.MemberDigest = digestBytes([]byte("other"))
		},
		"case subset": func(_ *ExpectedEvaluation, e *EvaluationEvidence) {
			e.Evaluation.Cases = e.Evaluation.Cases[:1]
			e.Results = e.Results[:1]
		},
		"case order": func(_ *ExpectedEvaluation, e *EvaluationEvidence) {
			e.Evaluation.Cases[0], e.Evaluation.Cases[1] = e.Evaluation.Cases[1], e.Evaluation.Cases[0]
		},
		"missing observation": func(_ *ExpectedEvaluation, e *EvaluationEvidence) {
			e.Results[0].Runs[0].Assertions = e.Results[0].Runs[0].Assertions[:0]
		},
	} {
		t.Run(name, func(t *testing.T) {
			l, x, r := flowEvidenceFixture(t)
			mutate(&x, &r)
			code := "coverage"
			if name == "destination configuration" || name == "member digest" {
				code = "subject"
			}
			flowEvidenceCode(t, l, x, evidenceBytes(t, r), code)
		})
	}
	// Changing only the flow changes the enclosing raw OCI subject. Updating
	// expectations and claims together is outside unsigned consistency proof.
	root := writeFlowSuite(t)
	rewriteFlow(t, root, func(f *FlowV1Alpha1) { f.Cases[0].Input = "Changed interaction input" })
	changed := writeTestOCILayout(t, root)
	flowEvidenceCode(t, changed, expected, raw, "subject")
}

func TestFlowV1Alpha1EvidenceCannotBypassCriticalRefusal(t *testing.T) {
	_, expected, e := flowEvidenceFixture(t)
	root := writeFlowSuite(t)
	var suite Suite
	readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
	suite.Extensions = append(suite.Extensions, Extension{Name: "unknown.critical", Critical: true})
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
	layout := writeTestOCILayout(t, root)
	var index ociIndex
	readStrictJSON(t, filepath.Join(layout, "index.json"), &index)
	d := index.Manifests[0]
	expected.Subject.Manifest = EvidenceDescriptor{MediaType: d.MediaType, Digest: d.Digest, Size: d.Size}
	e.Subject.Manifest = expected.Subject.Manifest
	flowEvidenceCode(t, layout, expected, evidenceBytes(t, e), "artifact")
}

func flowEvidenceCode(t *testing.T, layout string, expected ExpectedEvaluation, raw []byte, code string) {
	t.Helper()
	got, err := VerifyEvaluationFlowV1Alpha1(layout, expected, bytes.NewReader(raw))
	var refusal *EvidenceRefusal
	if got != nil || !errors.As(err, &refusal) || refusal.Code != code {
		t.Fatalf("got summary=%+v error=%v; want %s", got, err, code)
	}
}
