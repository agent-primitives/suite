package agentsuite

import (
	"io"

	evidencepkg "github.com/agent-primitives/suite/evidence"
)

// VerifyEvaluation delegates to the shared evidence implementation.
//
// Deprecated: use evidence.VerifyEvaluation.
func VerifyEvaluation(layoutPath string, expected ExpectedEvaluation, evidenceReader io.Reader) (*VerifiedEvaluation, error) {
	return evidencepkg.VerifyEvaluation(layoutPath, expected, evidenceReader)
}

// VerifyEvaluationFlowV1Alpha1 delegates to the shared evidence implementation.
//
// Deprecated: use evidence.VerifyEvaluationFlowV1Alpha1.
func VerifyEvaluationFlowV1Alpha1(layout string, expected ExpectedEvaluation, evidence io.Reader) (*VerifiedEvaluation, error) {
	return evidencepkg.VerifyEvaluationFlowV1Alpha1(layout, expected, evidence)
}
