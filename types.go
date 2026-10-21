package agentsuite

import "github.com/agent-primitives/suite/core"

const (
	// Deprecated: use core.ExecutionSharedSandbox.
	ExecutionSharedSandbox = core.ExecutionSharedSandbox
	// Deprecated: use core.LayoutVersion.
	LayoutVersion = core.LayoutVersion
	// Deprecated: use core.MediaTypeAgent.
	MediaTypeAgent = core.MediaTypeAgent
	// Deprecated: use core.MediaTypeArtifact.
	MediaTypeArtifact = core.MediaTypeArtifact
	// Deprecated: use core.MediaTypeBuildProfile.
	MediaTypeBuildProfile = core.MediaTypeBuildProfile
	// Deprecated: use core.MediaTypeComposition.
	MediaTypeComposition = core.MediaTypeComposition
	// Deprecated: use core.MediaTypeContent.
	MediaTypeContent = core.MediaTypeContent
	// Deprecated: use core.MediaTypeEmptyConfig.
	MediaTypeEmptyConfig = core.MediaTypeEmptyConfig
	// Deprecated: use core.MediaTypeEvaluationCase.
	MediaTypeEvaluationCase = core.MediaTypeEvaluationCase
	// Deprecated: use core.MediaTypeEvaluationIndex.
	MediaTypeEvaluationIndex = core.MediaTypeEvaluationIndex
	// Deprecated: use core.MediaTypeInstructions.
	MediaTypeInstructions = core.MediaTypeInstructions
	// Deprecated: use core.MediaTypeJSONSchema.
	MediaTypeJSONSchema = core.MediaTypeJSONSchema
	// Deprecated: use core.MediaTypePolicyV1.
	MediaTypePolicyV1 = core.MediaTypePolicyV1
	// Deprecated: use core.MediaTypePolicyV2.
	MediaTypePolicyV2 = core.MediaTypePolicyV2
	// Deprecated: use core.MediaTypeRuntimeProfile.
	MediaTypeRuntimeProfile = core.MediaTypeRuntimeProfile
	// Deprecated: use core.MediaTypeSuite.
	MediaTypeSuite = core.MediaTypeSuite
	// Deprecated: use core.MediaTypeToolProvider.
	MediaTypeToolProvider = core.MediaTypeToolProvider
	// Deprecated: use core.MediaTypeToolProviderCatalog.
	MediaTypeToolProviderCatalog = core.MediaTypeToolProviderCatalog
	// Deprecated: use core.MediaTypeToolProviderComposition.
	MediaTypeToolProviderComposition = core.MediaTypeToolProviderComposition
	// Deprecated: use core.SpecVersion.
	SpecVersion = core.SpecVersion
)

// Agent is the portable core definition.
//
// Deprecated: use core.Agent.
type Agent = core.Agent

// AgentInvoke is the portable core definition.
//
// Deprecated: use core.AgentInvoke.
type AgentInvoke = core.AgentInvoke

// AgentPlatform is the portable core definition.
//
// Deprecated: use core.AgentPlatform.
type AgentPlatform = core.AgentPlatform

// BrokeredCredential is the portable core definition.
//
// Deprecated: use core.BrokeredCredential.
type BrokeredCredential = core.BrokeredCredential

// BuildProfile is the portable core definition.
//
// Deprecated: use core.BuildProfile.
type BuildProfile = core.BuildProfile

// Composition is the portable core definition.
//
// Deprecated: use core.Composition.
type Composition = core.Composition

// CompositionRef is the portable core definition.
//
// Deprecated: use core.CompositionRef.
type CompositionRef = core.CompositionRef

// CompositionSelection is the portable core definition.
//
// Deprecated: use core.CompositionSelection.
type CompositionSelection = core.CompositionSelection

// DelegatedAuthorization is the portable core definition.
//
// Deprecated: use core.DelegatedAuthorization.
type DelegatedAuthorization = core.DelegatedAuthorization

// Descriptor is the portable core definition.
//
// Deprecated: use core.Descriptor.
type Descriptor = core.Descriptor

// EnvironmentName is the portable core definition.
//
// Deprecated: use core.EnvironmentName.
type EnvironmentName = core.EnvironmentName

// EvaluationAssertion is the portable core definition.
//
// Deprecated: use core.EvaluationAssertion.
type EvaluationAssertion = core.EvaluationAssertion

// EvaluationCase is the portable core definition.
//
// Deprecated: use core.EvaluationCase.
type EvaluationCase = core.EvaluationCase

// EvaluationIndex is the portable core definition.
//
// Deprecated: use core.EvaluationIndex.
type EvaluationIndex = core.EvaluationIndex

// EvaluationLimits is the portable core definition.
//
// Deprecated: use core.EvaluationLimits.
type EvaluationLimits = core.EvaluationLimits

// Extension is the portable core definition.
//
// Deprecated: use core.Extension.
type Extension = core.Extension

// FileRef is the portable core definition.
//
// Deprecated: use core.FileRef.
type FileRef = core.FileRef

// InventoryEntry is the portable core definition.
//
// Deprecated: use core.InventoryEntry.
type InventoryEntry = core.InventoryEntry

// ManifestRef is the portable core definition.
//
// Deprecated: use core.ManifestRef.
type ManifestRef = core.ManifestRef

// ModelRequirement is the portable core definition.
//
// Deprecated: use core.ModelRequirement.
type ModelRequirement = core.ModelRequirement

// NetworkAccess is the portable core definition.
//
// Deprecated: use core.NetworkAccess.
type NetworkAccess = core.NetworkAccess

// Platform is the portable core definition.
//
// Deprecated: use core.Platform.
type Platform = core.Platform

// PlatformImage is the portable core definition.
//
// Deprecated: use core.PlatformImage.
type PlatformImage = core.PlatformImage

// RemoteHeader is the portable core definition.
//
// Deprecated: use core.RemoteHeader.
type RemoteHeader = core.RemoteHeader

// RemoteNetworkRequirement is the portable core definition.
//
// Deprecated: use core.RemoteNetworkRequirement.
type RemoteNetworkRequirement = core.RemoteNetworkRequirement

// RemoteTimeouts is the portable core definition.
//
// Deprecated: use core.RemoteTimeouts.
type RemoteTimeouts = core.RemoteTimeouts

// RemoteToolProvider is the portable core definition.
//
// Deprecated: use core.RemoteToolProvider.
type RemoteToolProvider = core.RemoteToolProvider

// Report is the portable core definition.
//
// Deprecated: use core.Report.
type Report = core.Report

// ResolvedToolProvider is the portable core definition.
//
// Deprecated: use core.ResolvedToolProvider.
type ResolvedToolProvider = core.ResolvedToolProvider

// RuntimeRequirement is the portable core definition.
//
// Deprecated: use core.RuntimeRequirement.
type RuntimeRequirement = core.RuntimeRequirement

// SecretKeyRef is the portable core definition.
//
// Deprecated: use core.SecretKeyRef.
type SecretKeyRef = core.SecretKeyRef

// Suite is the portable core definition.
//
// Deprecated: use core.Suite.
type Suite = core.Suite

// Tool is the portable core definition.
//
// Deprecated: use core.Tool.
type Tool = core.Tool

// ToolProvider is the portable core definition.
//
// Deprecated: use core.ToolProvider.
type ToolProvider = core.ToolProvider

// ToolProviderCatalog is the portable core definition.
//
// Deprecated: use core.ToolProviderCatalog.
type ToolProviderCatalog = core.ToolProviderCatalog

// ToolProviderComposition is the portable core definition.
//
// Deprecated: use core.ToolProviderComposition.
type ToolProviderComposition = core.ToolProviderComposition

// ToolProviderCompositionRef is the portable core definition.
//
// Deprecated: use core.ToolProviderCompositionRef.
type ToolProviderCompositionRef = core.ToolProviderCompositionRef

// ToolProviderDependency is the portable core definition.
//
// Deprecated: use core.ToolProviderDependency.
type ToolProviderDependency = core.ToolProviderDependency

// ToolProviderRequirement is the portable core definition.
//
// Deprecated: use core.ToolProviderRequirement.
type ToolProviderRequirement = core.ToolProviderRequirement

// ToolProviderVariant is the portable core definition.
//
// Deprecated: use core.ToolProviderVariant.
type ToolProviderVariant = core.ToolProviderVariant
