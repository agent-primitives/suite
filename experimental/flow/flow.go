// Package flow explicitly selects the experimental kmx.flow/v1alpha1 stored graph contract. It does not execute flows or grant approval.
//
// Types alias the shared internal implementation so graph, evidence and diff
// algorithms can retain their private validated state. Defining-package names
// in reflection refer to that implementation, and pkg.go.dev may show aliases
// rather than their fields. Portable manifest fields are documented in core.
package flow

import (
	"github.com/agent-primitives/suite/internal/artifact"
)

// FlowExtensionV1Alpha1 aliases the shared implementation; see the package documentation.
const FlowExtensionV1Alpha1 = artifact.FlowExtensionV1Alpha1

// FlowPathV1Alpha1 aliases the shared implementation; see the package documentation.
const FlowPathV1Alpha1 = artifact.FlowPathV1Alpha1

// FlowVersionV1Alpha1 aliases the shared implementation; see the package documentation.
const FlowVersionV1Alpha1 = artifact.FlowVersionV1Alpha1

// FlowAssertionV1Alpha1 aliases the shared implementation; see the package documentation.
type FlowAssertionV1Alpha1 = artifact.FlowAssertionV1Alpha1

// FlowCaseV1Alpha1 aliases the shared implementation; see the package documentation.
type FlowCaseV1Alpha1 = artifact.FlowCaseV1Alpha1

// FlowEdgeRequirementV1Alpha1 aliases the shared implementation; see the package documentation.
type FlowEdgeRequirementV1Alpha1 = artifact.FlowEdgeRequirementV1Alpha1

// FlowInputV1Alpha1 aliases the shared implementation; see the package documentation.
type FlowInputV1Alpha1 = artifact.FlowInputV1Alpha1

// FlowStepV1Alpha1 aliases the shared implementation; see the package documentation.
type FlowStepV1Alpha1 = artifact.FlowStepV1Alpha1

// FlowV1Alpha1 aliases the shared implementation; see the package documentation.
type FlowV1Alpha1 = artifact.FlowV1Alpha1

// FlowV1Alpha1Graph aliases the shared implementation; see the package documentation.
type FlowV1Alpha1Graph = artifact.FlowV1Alpha1Graph

// ValidatePathFlowV1Alpha1 delegates to the shared artifact implementation.
func ValidatePathFlowV1Alpha1(path string) (*FlowV1Alpha1Graph, error) {
	return artifact.ValidatePathFlowV1Alpha1(path)
}

// ValidateDirectoryFlowV1Alpha1 delegates to the shared artifact implementation.
func ValidateDirectoryFlowV1Alpha1(root string) (*FlowV1Alpha1Graph, error) {
	return artifact.ValidateDirectoryFlowV1Alpha1(root)
}
