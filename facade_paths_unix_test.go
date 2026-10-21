//go:build unix

package agentsuite_test

import (
	"reflect"
	"testing"

	agentsuite "github.com/agent-primitives/suite"
	"github.com/agent-primitives/suite/experimental/flow"
	"github.com/agent-primitives/suite/oci"
)

// Native Windows success/security paths are built with protected ACL fixtures
// in internal/artifact; checkout fixtures have no such ACL guarantee.
func TestFacadeDirectoryAndDiff(t *testing.T) {
	const path = "testdata/minimal"
	before, err := agentsuite.ValidateDirectory(path)
	if err != nil {
		t.Fatal(err)
	}
	after, err := oci.ValidateDirectory(path)
	if err != nil || !reflect.DeepEqual(before, after) {
		t.Fatalf("directory differs: %v %v", after, err)
	}
	detected, err := oci.ValidatePath(path)
	if err != nil || !reflect.DeepEqual(after, detected) {
		t.Fatalf("path differs: %v %v", detected, err)
	}
	old, err := agentsuite.DiffPaths(path, path)
	if err != nil {
		t.Fatal(err)
	}
	current, err := oci.DiffPaths(path, path)
	if err != nil || !reflect.DeepEqual(old, current) || current.HasChanges() {
		t.Fatalf("diff differs: %v %v", current, err)
	}
	// Default validation accepts this core graph; explicit flow must not silently
	// fall back when its critical selector is missing.
	_, oldErr := agentsuite.ValidateDirectoryFlowV1Alpha1(path)
	_, newErr := flow.ValidateDirectoryFlowV1Alpha1(path)
	if oldErr == nil || newErr == nil || oldErr.Error() != newErr.Error() {
		t.Fatalf("explicit flow refusal differs: %v %v", oldErr, newErr)
	}
	_, pathErr := flow.ValidatePathFlowV1Alpha1(path)
	if pathErr == nil || pathErr.Error() != newErr.Error() {
		t.Fatalf("flow path silently changed contract: %v", pathErr)
	}
}
