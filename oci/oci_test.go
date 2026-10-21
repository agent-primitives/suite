package oci_test

import (
	"path/filepath"
	"testing"

	"github.com/agent-primitives/suite/core"
	"github.com/agent-primitives/suite/oci"
)

func TestTransportConstants(t *testing.T) {
	if oci.LayoutVersion != core.LayoutVersion || oci.MediaTypeArtifact != core.MediaTypeArtifact || oci.MediaTypeEmptyConfig != core.MediaTypeEmptyConfig || oci.MediaTypeContent != core.MediaTypeContent {
		t.Fatal("transport vocabulary changed from the canonical core constants")
	}
}

func TestMissingContentRefuses(t *testing.T) {
	missing := filepath.Join(t.TempDir(), "absent")
	if report, err := oci.ValidateDirectory(missing); err == nil || report != nil {
		t.Fatalf("directory accepted missing content: %v %v", report, err)
	}
	if report, err := oci.ValidatePath(missing); err == nil || report != nil {
		t.Fatalf("path accepted missing content: %v %v", report, err)
	}
	if _, err := oci.DiffPaths(missing, missing); err == nil {
		t.Fatal("diff accepted missing content")
	}
}
