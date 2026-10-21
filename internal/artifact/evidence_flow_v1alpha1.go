package artifact

import "io"

// VerifyEvaluationFlowV1Alpha1 checks unchanged evidence-v1 claims for one
// member against an original OCI artifact under the explicit critical-flow
// contract. It does not verify whole-flow results, runtime support or approval.
// Expectations must be independently resolved; destination bindings belong in
// the caller's non-secret execution-configuration projection. Like the default
// verifier, it establishes unsigned consistency, never evaluator authenticity.
func VerifyEvaluationFlowV1Alpha1(layout string, expected ExpectedEvaluation, evidence io.Reader) (*VerifiedEvaluation, error) {
	return verifyEvaluation(layout, expected, evidence, true)
}
