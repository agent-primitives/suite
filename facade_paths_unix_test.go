//go:build unix

package agentsuite_test

import (
	"reflect"
	"strings"
	"testing"

	"github.com/agent-primitives/suite/core"
	"github.com/agent-primitives/suite/experimental/flow"
	"github.com/agent-primitives/suite/oci"
)

// Native Windows success/security paths are built with protected ACL fixtures
// in internal/artifact; checkout fixtures have no such ACL guarantee.
func TestFacadeDirectoryAndDiff(t *testing.T) {
	const path = "testdata/minimal"
	report, err := oci.ValidateDirectory(path)
	if err != nil {
		t.Fatal(err)
	}
	if report.Name != "minimal" || report.Agents != 1 || report.Compositions != 1 {
		t.Fatalf("unexpected minimal report: %+v", report)
	}
	detected, err := oci.ValidatePath(path)
	if err != nil || !reflect.DeepEqual(report, detected) {
		t.Fatalf("path differs: %v %v", detected, err)
	}
	current, err := oci.DiffPaths(path, path)
	if err != nil {
		t.Fatal(err)
	}
	if current.HasChanges() || current.Summary != (oci.DiffSummary{}) || current.Before != current.After || !core.IsValidDigest(current.Before.ContentDigest) {
		t.Fatalf("self-diff changed identity: %+v", current)
	}
	// Default validation accepts this core graph; explicit flow must not silently
	// fall back when its critical selector is missing.
	for _, validate := range []func(string) (*flow.FlowV1Alpha1Graph, error){flow.ValidateDirectoryFlowV1Alpha1, flow.ValidatePathFlowV1Alpha1} {
		graph, err := validate(path)
		if graph != nil || err == nil || !strings.Contains(err.Error(), "experimental flow selector is missing") {
			t.Fatalf("explicit flow must refuse missing selector: %v %v", graph, err)
		}
	}
}
