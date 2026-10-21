package evidence_test

import (
	"errors"
	"io"
	"testing"

	"github.com/agent-primitives/suite/evidence"
)

func TestMissingExpectationsRefuse(t *testing.T) {
	for _, verify := range []func(string, evidence.ExpectedEvaluation, io.Reader) (*evidence.VerifiedEvaluation, error){evidence.VerifyEvaluation, evidence.VerifyEvaluationFlowV1Alpha1} {
		result, err := verify("unused", evidence.ExpectedEvaluation{}, nil)
		var refusal *evidence.EvidenceRefusal
		if result != nil || !errors.As(err, &refusal) || refusal.Code != "missing" {
			t.Fatalf("missing expectations: %v %v", result, err)
		}
	}
}
