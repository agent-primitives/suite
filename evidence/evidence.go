// Package evidence decodes and verifies unsigned evaluation claims against a local OCI layout. It does not execute agents or authenticate the evaluator.
//
// Types alias the shared internal implementation so graph, evidence and diff
// algorithms can retain their private validated state. Defining-package names
// in reflection refer to that implementation, and pkg.go.dev may show aliases
// rather than their fields. Portable manifest fields are documented in core.
package evidence

import (
	"io"

	"github.com/agent-primitives/suite/core"
	"github.com/agent-primitives/suite/internal/artifact"
)

// EvidenceJudgePolicyID aliases the shared implementation; see the package documentation.
const EvidenceJudgePolicyID = artifact.EvidenceJudgePolicyID

// EvidenceJudgePolicyVersion aliases the shared implementation; see the package documentation.
const EvidenceJudgePolicyVersion = artifact.EvidenceJudgePolicyVersion

// EvidencePolicyID aliases the shared implementation; see the package documentation.
const EvidencePolicyID = artifact.EvidencePolicyID

// EvidencePolicyVersion aliases the shared implementation; see the package documentation.
const EvidencePolicyVersion = artifact.EvidencePolicyVersion

// EvidenceSchemaVersion aliases the shared implementation; see the package documentation.
const EvidenceSchemaVersion = artifact.EvidenceSchemaVersion

// MediaTypeEvaluationEvidence aliases the shared implementation; see the package documentation.
const MediaTypeEvaluationEvidence = artifact.MediaTypeEvaluationEvidence

// EvaluationEvidence aliases the shared implementation; see the package documentation.
type EvaluationEvidence = artifact.EvaluationEvidence

// EvidenceAssertionResult aliases the shared implementation; see the package documentation.
type EvidenceAssertionResult = artifact.EvidenceAssertionResult

// EvidenceCaseRef aliases the shared implementation; see the package documentation.
type EvidenceCaseRef = artifact.EvidenceCaseRef

// EvidenceCaseResult aliases the shared implementation; see the package documentation.
type EvidenceCaseResult = artifact.EvidenceCaseResult

// EvidenceDescriptor aliases the shared implementation; see the package documentation.
type EvidenceDescriptor = artifact.EvidenceDescriptor

// EvidenceEvaluation aliases the shared implementation; see the package documentation.
type EvidenceEvaluation = artifact.EvidenceEvaluation

// EvidenceEvaluator aliases the shared implementation; see the package documentation.
type EvidenceEvaluator = artifact.EvidenceEvaluator

// EvidenceEvaluatorIdentity aliases the shared implementation; see the package documentation.
type EvidenceEvaluatorIdentity = artifact.EvidenceEvaluatorIdentity

// EvidenceExecution aliases the shared implementation; see the package documentation.
type EvidenceExecution = artifact.EvidenceExecution

// EvidenceFileRef aliases the shared implementation; see the package documentation.
type EvidenceFileRef = artifact.EvidenceFileRef

// EvidenceImplementation is core's portable implementation identity.
type EvidenceImplementation = core.EvidenceImplementation

// EvidenceJudgeConfiguration aliases the shared implementation; see the package documentation.
type EvidenceJudgeConfiguration = artifact.EvidenceJudgeConfiguration

// EvidenceJudgeResult aliases the shared implementation; see the package documentation.
type EvidenceJudgeResult = artifact.EvidenceJudgeResult

// EvidenceModel aliases the shared implementation; see the package documentation.
type EvidenceModel = artifact.EvidenceModel

// EvidencePlatform aliases the shared implementation; see the package documentation.
type EvidencePlatform = artifact.EvidencePlatform

// EvidencePolicy aliases the shared implementation; see the package documentation.
type EvidencePolicy = artifact.EvidencePolicy

// EvidenceRefusal aliases the shared implementation; see the package documentation.
type EvidenceRefusal = artifact.EvidenceRefusal

// EvidenceRunResult aliases the shared implementation; see the package documentation.
type EvidenceRunResult = artifact.EvidenceRunResult

// EvidenceSubject aliases the shared implementation; see the package documentation.
type EvidenceSubject = artifact.EvidenceSubject

// ExpectedEvaluation aliases the shared implementation; see the package documentation.
type ExpectedEvaluation = artifact.ExpectedEvaluation

// VerifiedEvaluation aliases the shared implementation; see the package documentation.
type VerifiedEvaluation = artifact.VerifiedEvaluation

// VerifyEvaluation delegates to the shared artifact implementation.
func VerifyEvaluation(layoutPath string, expected ExpectedEvaluation, evidenceReader io.Reader) (*VerifiedEvaluation, error) {
	return artifact.VerifyEvaluation(layoutPath, expected, evidenceReader)
}

// VerifyEvaluationFlowV1Alpha1 delegates to the shared artifact implementation.
func VerifyEvaluationFlowV1Alpha1(layout string, expected ExpectedEvaluation, evidence io.Reader) (*VerifiedEvaluation, error) {
	return artifact.VerifyEvaluationFlowV1Alpha1(layout, expected, evidence)
}
