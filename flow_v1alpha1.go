package agentsuite

import "github.com/agent-primitives/suite/experimental/flow"

// FlowV1Alpha1Graph is the flow definition.
//
// Deprecated: use flow.FlowV1Alpha1Graph.
type FlowV1Alpha1Graph = flow.FlowV1Alpha1Graph

// ValidatePathFlowV1Alpha1 delegates to the shared flow implementation.
//
// Deprecated: use flow.ValidatePathFlowV1Alpha1.
func ValidatePathFlowV1Alpha1(path string) (*FlowV1Alpha1Graph, error) {
	return flow.ValidatePathFlowV1Alpha1(path)
}

// ValidateDirectoryFlowV1Alpha1 delegates to the shared flow implementation.
//
// Deprecated: use flow.ValidateDirectoryFlowV1Alpha1.
func ValidateDirectoryFlowV1Alpha1(root string) (*FlowV1Alpha1Graph, error) {
	return flow.ValidateDirectoryFlowV1Alpha1(root)
}
