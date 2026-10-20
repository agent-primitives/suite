//go:build !unix && !windows

package agentsuite

import (
	"strings"
	"testing"
)

func TestUnsupportedDirectorySecurity(t *testing.T) {
	root := writeIdentityFixture(t)
	if _, err := ValidateDirectory(root); err == nil || !strings.Contains(err.Error(), "unsupported") {
		t.Fatalf("ValidateDirectory = %v, want unsupported-platform refusal", err)
	}
	if err := checkDirectoryLink(); err == nil || !strings.Contains(err.Error(), "unsupported") {
		t.Fatalf("checkDirectoryLink = %v, want unsupported-platform refusal", err)
	}
}
