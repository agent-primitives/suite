//go:build unix

package artifact

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLooseDirectoryUnixSecurityRefusals(t *testing.T) {
	for _, name := range []string{".", "instructions", "instructions/writer.md"} {
		for _, mode := range []os.FileMode{0777, 0775, 0757, 0755 | os.ModeSetuid, 0755 | os.ModeSetgid, 0755 | os.ModeSticky} {
			t.Run(fmt.Sprintf("%s/%o", name, mode), func(t *testing.T) {
				root := writeIdentityFixture(t)
				if err := os.Chmod(filepath.Join(root, name), mode); err != nil {
					t.Fatal(err)
				}
				if _, err := ValidateDirectory(root); err == nil || !(strings.Contains(err.Error(), "unsafe file mode") || strings.Contains(err.Error(), "setid or sticky")) {
					t.Fatalf("ValidateDirectory = %v, want unsafe-mode refusal", err)
				}
			})
		}
	}
}

func TestLooseDirectoryUnixSafeDirectoryModes(t *testing.T) {
	const golden = "sha256:15e0613bf11e7c70e2255a7f669381343656b0957a9231d0b92e189bf254f3fb"
	for _, mode := range []os.FileMode{0700, 0750, 0755} {
		t.Run(fmt.Sprintf("%o", mode), func(t *testing.T) {
			root := writeIdentityFixture(t)
			for _, name := range []string{".", "instructions"} {
				if err := os.Chmod(filepath.Join(root, name), mode); err != nil {
					t.Fatal(err)
				}
			}
			report, err := DiffPaths(root, root)
			if err != nil {
				t.Fatal(err)
			}
			if report.Before.ContentDigest != golden {
				t.Fatalf("identity = %s, want %s", report.Before.ContentDigest, golden)
			}
		})
	}
}
