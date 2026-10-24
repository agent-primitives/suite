package artifact

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func writeIdentityFixture(t *testing.T) string {
	t.Helper()
	return copyAgentSuiteDirectory(t, filepath.Join("..", "..", "testdata", "minimal"))
}

func TestLooseDirectoryIdentityGolden(t *testing.T) {
	golden := packageConformanceNamed(t, "minimal").ContentDigest
	for _, mode := range []os.FileMode{0444, 0600, 0644, 0700, 0755} {
		t.Run(fmt.Sprintf("%o", mode), func(t *testing.T) {
			root := writeIdentityFixture(t)
			// Restore writable attributes before TempDir cleanup on Windows.
			t.Cleanup(func() {
				if err := filepath.WalkDir(root, func(name string, d os.DirEntry, err error) error {
					if err != nil {
						return err
					}
					if d.Type().IsRegular() {
						return os.Chmod(name, 0600)
					}
					return nil
				}); err != nil {
					t.Error(err)
				}
			})
			if err := filepath.WalkDir(root, func(name string, d os.DirEntry, err error) error {
				if err != nil {
					return err
				}
				if d.Type().IsRegular() {
					return os.Chmod(name, mode)
				}
				return nil
			}); err != nil {
				t.Fatal(err)
			}
			secureDirectoryFixture(t, root)
			if _, err := ValidateDirectory(root); err != nil {
				t.Fatal(err)
			}
			report, err := DiffPaths(root, root)
			if err != nil {
				t.Fatal(err)
			}
			if report.Before.ContentDigest != golden || report.After.ContentDigest != golden || report.HasChanges() {
				t.Fatalf("loose identity=%s / %s, changes=%v; want %s", report.Before.ContentDigest, report.After.ContentDigest, report.HasChanges(), golden)
			}
		})
	}
}

func TestLooseDirectoryDeclaredModeIgnoresHostMode(t *testing.T) {
	before, after := writeIdentityFixture(t), writeIdentityFixture(t)
	for _, root := range []string{before, after} {
		addLargeDiffToolProvider(t, root, 1)
	}
	file := filepath.Join(after, "tool-providers/large/1.0.0/linux-amd64/bin/tool-0000")
	if err := os.Chmod(file, 0600); err != nil {
		t.Fatal(err)
	}
	secureDirectoryFixture(t, before)
	secureDirectoryFixture(t, after)
	report, err := DiffPaths(before, after)
	if err != nil {
		t.Fatal(err)
	}
	if report.HasChanges() || report.Before.ContentDigest != report.After.ContentDigest {
		t.Fatalf("host permissions changed declared identity: %+v", report)
	}
}

func TestLooseDirectoryConflictingDeclarationsRefuse(t *testing.T) {
	root := writeIdentityFixture(t)
	addLargeDiffToolProvider(t, root, 1)
	secureDirectoryFixture(t, root)
	content, err := loadDirectory(root)
	if err != nil {
		t.Fatal(err)
	}
	v, _, err := validateContentGraph(content)
	if err != nil {
		t.Fatal(err)
	}
	variant := v.toolProviders["large@1.0.0"].Variants[0]
	variant.Files[0].Mode = 0700
	variant.VariantDigest = mustVariantDigest(t, variant)
	if err := validateVariant(variant, variant.VariantDigest, content); err == nil || !strings.Contains(err.Error(), "conflicting declared mode") {
		t.Fatalf("conflicting inventory mode: %v", err)
	}
}

func TestLooseDirectoryDeclaredDirectoryMetadata(t *testing.T) {
	root := writeIdentityFixture(t)
	addLargeDiffToolProvider(t, root, 1)
	secureDirectoryFixture(t, root)
	content, err := loadDirectory(root)
	if err != nil {
		t.Fatal(err)
	}
	v, _, err := validateContentGraph(content)
	if err != nil {
		t.Fatal(err)
	}
	variant := v.toolProviders["large@1.0.0"].Variants[0]
	variant.Files = append(variant.Files, InventoryEntry{Path: "bin", Type: "directory", Mode: 0700})
	variant.VariantDigest = mustVariantDigest(t, variant)
	if err := validateVariant(variant, variant.VariantDigest, content); err != nil {
		t.Fatal(err)
	}
	entry := content.entries["tool-providers/large/1.0.0/linux-amd64/bin"]
	if entry.Mode != 0700 || entry.Size != 0 {
		t.Fatalf("declared directory metadata: mode=%o size=%d", entry.Mode, entry.Size)
	}
}

func TestPublishedArtifactInventoryModesRemainExact(t *testing.T) {
	if packageConformanceNamed(t, "inventory-mode-mismatch").Valid {
		t.Fatal("inventory-mode-mismatch must be a refusal case")
	}
	for _, c := range packageConformanceCases(t) {
		if c.Form != "oci" || c.Valid {
			continue
		}
		t.Run(c.Name, func(t *testing.T) {
			// Error text is a Go-side assertion, not a cross-language contract.
			want := map[string]string{"inventory-mode-mismatch": "does not match payload metadata"}[c.Name]
			if want == "" {
				t.Fatalf("add a refusal assertion for OCI case %q", c.Name)
			}
			if _, err := ValidatePath(packageConformanceInput(t, c)); err == nil || !strings.Contains(err.Error(), want) {
				t.Fatalf("archive refusal: %v; want %q", err, want)
			}
		})
	}
}

func TestPublishedArtifactIdentityGolden(t *testing.T) {
	count := 0
	for _, c := range packageConformanceCases(t) {
		if c.Form != "oci" || !c.Valid {
			continue
		}
		count++
		t.Run(c.Name, func(t *testing.T) {
			layout := packageConformanceInput(t, c)
			report, err := DiffPaths(layout, layout)
			if err != nil {
				t.Fatal(err)
			}
			if report.Before.ContentDigest != c.ContentDigest || report.Before.ArtifactDigest != c.ManifestDigest {
				t.Fatalf("artifact identity=%+v; want content=%s manifest=%s", report.Before, c.ContentDigest, c.ManifestDigest)
			}
		})
	}
	if count < 3 {
		t.Fatalf("OCI identity corpus has %d cases, want at least 3", count)
	}
}
