package agentsuite

import (
	"io"

	"github.com/agent-primitives/suite/core"
	evidencepkg "github.com/agent-primitives/suite/evidence"
	"github.com/agent-primitives/suite/experimental/flow"
	"github.com/agent-primitives/suite/oci"
)

const (
	ExecutionSharedSandbox           = core.ExecutionSharedSandbox
	LayoutVersion                    = core.LayoutVersion
	MediaTypeAgent                   = core.MediaTypeAgent
	MediaTypeArtifact                = core.MediaTypeArtifact
	MediaTypeBuildProfile            = core.MediaTypeBuildProfile
	MediaTypeComposition             = core.MediaTypeComposition
	MediaTypeContent                 = core.MediaTypeContent
	MediaTypeEmptyConfig             = core.MediaTypeEmptyConfig
	MediaTypeEvaluationCase          = core.MediaTypeEvaluationCase
	MediaTypeEvaluationIndex         = core.MediaTypeEvaluationIndex
	MediaTypeInstructions            = core.MediaTypeInstructions
	MediaTypeJSONSchema              = core.MediaTypeJSONSchema
	MediaTypePolicyV1                = core.MediaTypePolicyV1
	MediaTypePolicyV2                = core.MediaTypePolicyV2
	MediaTypeRuntimeProfile          = core.MediaTypeRuntimeProfile
	MediaTypeSuite                   = core.MediaTypeSuite
	MediaTypeToolProvider            = core.MediaTypeToolProvider
	MediaTypeToolProviderCatalog     = core.MediaTypeToolProviderCatalog
	MediaTypeToolProviderComposition = core.MediaTypeToolProviderComposition
	SpecVersion                      = core.SpecVersion
)

// Agent is the portable core definition.
type Agent = core.Agent

// AgentInvoke is the portable core definition.
type AgentInvoke = core.AgentInvoke

// AgentPlatform is the portable core definition.
type AgentPlatform = core.AgentPlatform

// BrokeredCredential is the portable core definition.
type BrokeredCredential = core.BrokeredCredential

// BuildProfile is the portable core definition.
type BuildProfile = core.BuildProfile

// Composition is the portable core definition.
type Composition = core.Composition

// CompositionRef is the portable core definition.
type CompositionRef = core.CompositionRef

// CompositionSelection is the portable core definition.
type CompositionSelection = core.CompositionSelection

// DelegatedAuthorization is the portable core definition.
type DelegatedAuthorization = core.DelegatedAuthorization

// Descriptor is the portable core definition.
type Descriptor = core.Descriptor

// EnvironmentName is the portable core definition.
type EnvironmentName = core.EnvironmentName

// EvaluationAssertion is the portable core definition.
type EvaluationAssertion = core.EvaluationAssertion

// EvaluationCase is the portable core definition.
type EvaluationCase = core.EvaluationCase

// EvaluationIndex is the portable core definition.
type EvaluationIndex = core.EvaluationIndex

// EvaluationLimits is the portable core definition.
type EvaluationLimits = core.EvaluationLimits

// Extension is the portable core definition.
type Extension = core.Extension

// FileRef is the portable core definition.
type FileRef = core.FileRef

// InventoryEntry is the portable core definition.
type InventoryEntry = core.InventoryEntry

// ManifestRef is the portable core definition.
type ManifestRef = core.ManifestRef

// ModelRequirement is the portable core definition.
type ModelRequirement = core.ModelRequirement

// NetworkAccess is the portable core definition.
type NetworkAccess = core.NetworkAccess

// Platform is the portable core definition.
type Platform = core.Platform

// PlatformImage is the portable core definition.
type PlatformImage = core.PlatformImage

// RemoteHeader is the portable core definition.
type RemoteHeader = core.RemoteHeader

// RemoteNetworkRequirement is the portable core definition.
type RemoteNetworkRequirement = core.RemoteNetworkRequirement

// RemoteTimeouts is the portable core definition.
type RemoteTimeouts = core.RemoteTimeouts

// RemoteToolProvider is the portable core definition.
type RemoteToolProvider = core.RemoteToolProvider

// Report is the portable core definition.
type Report = core.Report

// ResolvedToolProvider is the portable core definition.
type ResolvedToolProvider = core.ResolvedToolProvider

// RuntimeRequirement is the portable core definition.
type RuntimeRequirement = core.RuntimeRequirement

// SecretKeyRef is the portable core definition.
type SecretKeyRef = core.SecretKeyRef

// Suite is the portable core definition.
type Suite = core.Suite

// Tool is the portable core definition.
type Tool = core.Tool

// ToolProvider is the portable core definition.
type ToolProvider = core.ToolProvider

// ToolProviderCatalog is the portable core definition.
type ToolProviderCatalog = core.ToolProviderCatalog

// ToolProviderComposition is the portable core definition.
type ToolProviderComposition = core.ToolProviderComposition

// ToolProviderCompositionRef is the portable core definition.
type ToolProviderCompositionRef = core.ToolProviderCompositionRef

// ToolProviderDependency is the portable core definition.
type ToolProviderDependency = core.ToolProviderDependency

// ToolProviderRequirement is the portable core definition.
type ToolProviderRequirement = core.ToolProviderRequirement

// ToolProviderVariant is the portable core definition.
type ToolProviderVariant = core.ToolProviderVariant

const ExecutionHTTPV1 = core.ExecutionHTTPV1

const AgentKitMountedConfig = core.AgentKitMountedConfig

// ExecutionContract is the portable core definition.
type ExecutionContract = core.ExecutionContract

// ExecutionInput is the portable core definition.
type ExecutionInput = core.ExecutionInput

// ValidateExecutionContract checks a portable execution declaration.
func ValidateExecutionContract(c ExecutionContract) error { return core.ValidateExecutionContract(c) }

// InferenceRequirements is the portable core definition.
type InferenceRequirements = core.InferenceRequirements

// ValidateImageReference checks a registry-qualified, sha256-digested image reference.
func ValidateImageReference(value string) error { return core.ValidateImageReference(value) }

// RuntimeProfile is the portable core definition.
type RuntimeProfile = core.RuntimeProfile

// Marshal delegates to the shared core implementation.
func Marshal(value any) ([]byte, error) { return core.Marshal(value) }

// Unmarshal delegates to the shared core implementation.
func Unmarshal(data []byte, out any) error { return core.Unmarshal(data, out) }

// Digest delegates to the shared core implementation.
func Digest(data []byte) (string, error) { return core.Digest(data) }

// DescriptorSizeAndDigestMatch delegates to the shared core implementation.
func DescriptorSizeAndDigestMatch(data []byte, descriptor Descriptor) bool {
	return core.DescriptorSizeAndDigestMatch(data, descriptor)
}

// MatchesCanonicalDescriptor delegates to the shared core implementation.
func MatchesCanonicalDescriptor(data []byte, descriptor Descriptor) bool {
	return core.MatchesCanonicalDescriptor(data, descriptor)
}

// IsValidDigest delegates to the shared core implementation.
func IsValidDigest(value string) bool { return core.IsValidDigest(value) }

// ValidatePath delegates to the shared oci implementation.
func ValidatePath(value string) (*core.Report, error) { return oci.ValidatePath(value) }

// ValidateDirectory delegates to the shared oci implementation.
func ValidateDirectory(root string) (*core.Report, error) { return oci.ValidateDirectory(root) }

// DiffAdded is the oci definition.
const DiffAdded = oci.DiffAdded

// DiffModified is the oci definition.
const DiffModified = oci.DiffModified

// DiffRemoved is the oci definition.
const DiffRemoved = oci.DiffRemoved

// DiffReportSchemaVersion is the oci definition.
const DiffReportSchemaVersion = oci.DiffReportSchemaVersion

// AffectedAgent is the oci definition.
type AffectedAgent = oci.AffectedAgent

// DiffIdentity is the oci definition.
type DiffIdentity = oci.DiffIdentity

// DiffLimitError is the oci definition.
type DiffLimitError = oci.DiffLimitError

// DiffReport is the oci definition.
type DiffReport = oci.DiffReport

// DiffSummary is the oci definition.
type DiffSummary = oci.DiffSummary

// FieldChange is the oci definition.
type FieldChange = oci.FieldChange

// RecordChange is the oci definition.
type RecordChange = oci.RecordChange

// DiffPaths delegates to the shared oci implementation.
func DiffPaths(beforePath, afterPath string) (DiffReport, error) {
	return oci.DiffPaths(beforePath, afterPath)
}

// EvidenceJudgePolicyID is the evidence definition.
const EvidenceJudgePolicyID = evidencepkg.EvidenceJudgePolicyID

// EvidenceJudgePolicyVersion is the evidence definition.
const EvidenceJudgePolicyVersion = evidencepkg.EvidenceJudgePolicyVersion

// EvidencePolicyID is the evidence definition.
const EvidencePolicyID = evidencepkg.EvidencePolicyID

// EvidencePolicyVersion is the evidence definition.
const EvidencePolicyVersion = evidencepkg.EvidencePolicyVersion

// EvidenceSchemaVersion is the evidence definition.
const EvidenceSchemaVersion = evidencepkg.EvidenceSchemaVersion

// MediaTypeEvaluationEvidence is the evidence definition.
const MediaTypeEvaluationEvidence = evidencepkg.MediaTypeEvaluationEvidence

// EvaluationEvidence is the evidence definition.
type EvaluationEvidence = evidencepkg.EvaluationEvidence

// EvidenceAssertionResult is the evidence definition.
type EvidenceAssertionResult = evidencepkg.EvidenceAssertionResult

// EvidenceCaseRef is the evidence definition.
type EvidenceCaseRef = evidencepkg.EvidenceCaseRef

// EvidenceCaseResult is the evidence definition.
type EvidenceCaseResult = evidencepkg.EvidenceCaseResult

// EvidenceDescriptor is the evidence definition.
type EvidenceDescriptor = evidencepkg.EvidenceDescriptor

// EvidenceEvaluation is the evidence definition.
type EvidenceEvaluation = evidencepkg.EvidenceEvaluation

// EvidenceEvaluator is the evidence definition.
type EvidenceEvaluator = evidencepkg.EvidenceEvaluator

// EvidenceEvaluatorIdentity is the evidence definition.
type EvidenceEvaluatorIdentity = evidencepkg.EvidenceEvaluatorIdentity

// EvidenceExecution is the evidence definition.
type EvidenceExecution = evidencepkg.EvidenceExecution

// EvidenceFileRef is the evidence definition.
type EvidenceFileRef = evidencepkg.EvidenceFileRef

// EvidenceImplementation is the portable core definition.
type EvidenceImplementation = core.EvidenceImplementation

// EvidenceJudgeConfiguration is the evidence definition.
type EvidenceJudgeConfiguration = evidencepkg.EvidenceJudgeConfiguration

// EvidenceJudgeResult is the evidence definition.
type EvidenceJudgeResult = evidencepkg.EvidenceJudgeResult

// EvidenceModel is the evidence definition.
type EvidenceModel = evidencepkg.EvidenceModel

// EvidencePlatform is the evidence definition.
type EvidencePlatform = evidencepkg.EvidencePlatform

// EvidencePolicy is the evidence definition.
type EvidencePolicy = evidencepkg.EvidencePolicy

// EvidenceRefusal is the evidence definition.
type EvidenceRefusal = evidencepkg.EvidenceRefusal

// EvidenceRunResult is the evidence definition.
type EvidenceRunResult = evidencepkg.EvidenceRunResult

// EvidenceSubject is the evidence definition.
type EvidenceSubject = evidencepkg.EvidenceSubject

// ExpectedEvaluation is the evidence definition.
type ExpectedEvaluation = evidencepkg.ExpectedEvaluation

// VerifiedEvaluation is the evidence definition.
type VerifiedEvaluation = evidencepkg.VerifiedEvaluation

// VerifyEvaluation delegates to the shared evidence implementation.
func VerifyEvaluation(layoutPath string, expected ExpectedEvaluation, evidenceReader io.Reader) (*VerifiedEvaluation, error) {
	return evidencepkg.VerifyEvaluation(layoutPath, expected, evidenceReader)
}

// VerifyEvaluationFlowV1Alpha1 delegates to the shared evidence implementation.
func VerifyEvaluationFlowV1Alpha1(layout string, expected ExpectedEvaluation, evidence io.Reader) (*VerifiedEvaluation, error) {
	return evidencepkg.VerifyEvaluationFlowV1Alpha1(layout, expected, evidence)
}

// FlowExtensionV1Alpha1 is the flow definition.
const FlowExtensionV1Alpha1 = flow.FlowExtensionV1Alpha1

// FlowPathV1Alpha1 is the flow definition.
const FlowPathV1Alpha1 = flow.FlowPathV1Alpha1

// FlowVersionV1Alpha1 is the flow definition.
const FlowVersionV1Alpha1 = flow.FlowVersionV1Alpha1

// FlowAssertionV1Alpha1 is the flow definition.
type FlowAssertionV1Alpha1 = flow.FlowAssertionV1Alpha1

// FlowCaseV1Alpha1 is the flow definition.
type FlowCaseV1Alpha1 = flow.FlowCaseV1Alpha1

// FlowEdgeRequirementV1Alpha1 is the flow definition.
type FlowEdgeRequirementV1Alpha1 = flow.FlowEdgeRequirementV1Alpha1

// FlowInputV1Alpha1 is the flow definition.
type FlowInputV1Alpha1 = flow.FlowInputV1Alpha1

// FlowStepV1Alpha1 is the flow definition.
type FlowStepV1Alpha1 = flow.FlowStepV1Alpha1

// FlowV1Alpha1 is the flow definition.
type FlowV1Alpha1 = flow.FlowV1Alpha1

// FlowV1Alpha1Graph is the flow definition.
type FlowV1Alpha1Graph = flow.FlowV1Alpha1Graph

// ValidatePathFlowV1Alpha1 delegates to the shared flow implementation.
func ValidatePathFlowV1Alpha1(path string) (*FlowV1Alpha1Graph, error) {
	return flow.ValidatePathFlowV1Alpha1(path)
}

// ValidateDirectoryFlowV1Alpha1 delegates to the shared flow implementation.
func ValidateDirectoryFlowV1Alpha1(root string) (*FlowV1Alpha1Graph, error) {
	return flow.ValidateDirectoryFlowV1Alpha1(root)
}
