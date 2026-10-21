package flow_test

import (
	"path/filepath"
	"testing"

	"github.com/agent-primitives/suite/experimental/flow"
)

func TestMissingContentRefuses(t *testing.T) {
	missing := filepath.Join(t.TempDir(), "absent")
	for _, validate := range []func(string) (*flow.FlowV1Alpha1Graph, error){flow.ValidateDirectoryFlowV1Alpha1, flow.ValidatePathFlowV1Alpha1} {
		if graph, err := validate(missing); err == nil || graph != nil {
			t.Fatalf("flow accepted missing content: %v %v", graph, err)
		}
	}
}
