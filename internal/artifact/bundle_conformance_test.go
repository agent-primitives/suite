package artifact

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

// These are frozen Go fixture promotions, not a second fixture implementation.
// bytes contains the complete original provider document (JSON base64 encoding).
// Entries are portable loader metadata BEFORE directory inventory-mode binding;
// payload bodies are deliberately not retained by this subsystem test.
// Closure/collision rows own only their named entry point, not variant identity
// or whole-package validity (a cycle cannot carry cryptographic self-pins).
type sharedBundleCases struct {
	Cases []sharedBundleCase `json:"cases"`
}

type sharedBundleCase struct {
	Name                 string                 `json:"name"`
	Scope                string                 `json:"scope"`
	GoEntryPoint         string                 `json:"goEntryPoint"`
	SourceType           string                 `json:"sourceType"`
	Providers            []sharedBundleProvider `json:"providers"`
	Entries              []sharedBundleEntry    `json:"entries"`
	RootKey              string                 `json:"rootKey"`
	Variant              int                    `json:"variant"`
	Valid                *bool                  `json:"valid"`
	Refusal              string                 `json:"refusal"`
	Order                []string               `json:"order,omitempty"`
	SupportedFullPackage bool                   `json:"supportedFullPackage,omitempty"`
}

type sharedBundleProvider struct {
	Key   string `json:"key"`
	File  string `json:"file"`
	Bytes string `json:"bytes"`
}

type sharedBundleEntry struct {
	Path       string `json:"path"`
	Type       string `json:"type"`
	Mode       uint32 `json:"mode"`
	UID        int    `json:"uid"`
	GID        int    `json:"gid"`
	Size       int64  `json:"size"`
	Digest     string `json:"digest"`
	LinkTarget string `json:"linkTarget"`
}

func (source sharedBundleProvider) rawBytes(t *testing.T) []byte {
	t.Helper()
	raw, err := base64.StdEncoding.Strict().DecodeString(source.Bytes)
	if err != nil || len(raw) == 0 {
		t.Fatalf("invalid provider bytes: %v", err)
	}
	return raw
}

func (row sharedBundleCase) content(t *testing.T) *contentSet {
	t.Helper()
	content := &contentSet{entries: map[string]contentEntry{}}
	switch row.SourceType {
	case "directory":
		content.sourceType = "directory"
	case "archive": // Archive metadata stays authoritative; no mode binding.
	default:
		t.Fatalf("unknown source type %q", row.SourceType)
	}
	previous := ""
	for _, e := range row.Entries {
		if e.Path <= previous || e.Type == "" {
			t.Fatalf("entries must have explicit types and strictly sorted paths: %+v", e)
		}
		previous = e.Path
		content.entries[e.Path] = contentEntry{Path: e.Path, Type: e.Type,
			Mode: e.Mode, UID: e.UID, GID: e.GID, Size: e.Size,
			Digest: e.Digest, LinkTarget: e.LinkTarget}
	}
	return content
}

func (row sharedBundleCase) evaluate(t *testing.T) ([]string, error) {
	t.Helper()
	providers := map[string]ToolProvider{}
	raw := map[string][]byte{}
	for _, source := range row.Providers {
		if _, err := validateContentPath(source.File); err != nil {
			t.Fatal(err)
		}
		sourceBytes := source.rawBytes(t)
		var provider ToolProvider
		if err := decodeStrict(sourceBytes, &provider); err != nil {
			return nil, err
		}
		if source.Key != provider.ID+"@"+provider.Version || raw[source.Key] != nil {
			t.Fatalf("invalid or duplicate provider key %q", source.Key)
		}
		providers[source.Key], raw[source.Key] = provider, sourceBytes
	}
	root, ok := providers[row.RootKey]
	if !ok || row.Variant < 0 || row.Variant >= len(root.Variants) {
		t.Fatal("root variant is absent")
	}
	variant := root.Variants[row.Variant]
	switch row.Scope {
	case "variant":
		if row.GoEntryPoint != "validateVariant" {
			t.Fatal("wrong variant entry point")
		}
		digests, err := rawVariantDigests(raw[row.RootKey])
		if err != nil {
			return nil, err
		}
		return nil, validateVariant(variant, digests[row.Variant], row.content(t))
	case "closure", "collision":
		want := "bundleClosure"
		if row.Scope == "collision" {
			want = "addVariantDestinations"
		}
		if row.GoEntryPoint != want {
			t.Fatal("wrong graph entry point")
		}
		selected, err := bundleClosure(row.RootKey, variant, providers)
		if err != nil {
			return nil, err
		}
		var order []string
		destinations := map[string]InventoryEntry{}
		for _, bundle := range selected {
			order = append(order, bundle.providerKey)
			if row.Scope == "collision" {
				if err := addVariantDestinations(destinations, bundle.variant); err != nil {
					return order, err
				}
			}
		}
		return order, nil
	default:
		t.Fatalf("unknown scope %q", row.Scope)
		return nil, nil
	}
}

func assertSharedBundleOutcome(t *testing.T, row sharedBundleCase, err error) {
	t.Helper()
	if row.Valid == nil {
		t.Fatal("missing explicit validity expectation")
	}
	if (err == nil) != *row.Valid || (!*row.Valid && (row.Refusal == "" || !strings.Contains(err.Error(), row.Refusal))) {
		t.Fatalf("%s: error = %v; want valid=%t, refusal=%q", row.GoEntryPoint, err, *row.Valid, row.Refusal)
	}
}

// Complete fixture rows additionally exercise public ValidatePath, preserving
// original raw variant fields while rebinding the catalog and suite descriptors.
// This corroborates the Go subsystem oracle, not Python whole-package parity.
func (row sharedBundleCase) fullValidatePath(t *testing.T) {
	t.Helper()
	if row.Scope != "variant" || row.SourceType != "directory" || len(row.Providers) != 1 {
		t.Fatal("unsupported complete fixture")
	}
	root, name, _, _ := inventoryPresenceFixture(t)
	source := row.Providers[0]
	if source.File != name {
		t.Fatal("complete fixture provider path changed")
	}
	sourceBytes := source.rawBytes(t)
	var document map[string]any
	if err := json.Unmarshal(sourceBytes, &document); err != nil {
		t.Fatal(err)
	}
	bindPresenceProvider(t, root, name, document)
	if !bytes.Equal(policyBindingRead(t, root, name), sourceBytes) {
		t.Fatal("complete fixture did not preserve literal provider bytes")
	}
	secureDirectoryFixture(t, root)
	_, err := ValidatePath(root)
	assertSharedBundleOutcome(t, row, err)
}

func TestSharedBundleCases(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "..", "testdata", "conformance", "bundle-cases.json"))
	if err != nil {
		t.Fatal(err)
	}
	var corpus sharedBundleCases
	if err := decodeStrict(data, &corpus); err != nil {
		t.Fatal(err)
	}
	counts := map[string]int{}
	names := map[string]bool{}
	for _, row := range corpus.Cases {
		if row.Name == "" || names[row.Name] || len(row.Providers) == 0 || row.Valid == nil {
			t.Fatalf("empty/duplicate case or absent providers: %q", row.Name)
		}
		names[row.Name] = true
		counts[row.Scope]++
		t.Run(row.Name, func(t *testing.T) {
			// Construct snapshots even for graph-only rows, to guard their shape.
			row.content(t)
			order, err := row.evaluate(t)
			assertSharedBundleOutcome(t, row, err)
			if *row.Valid && row.Scope == "closure" && !reflect.DeepEqual(order, row.Order) {
				t.Fatalf("DFS order = %v, want %v", order, row.Order)
			}
			if row.SupportedFullPackage {
				row.fullValidatePath(t)
			}
		})
	}
	// Exact counts prevent a missing scope/empty selection from becoming green.
	want := map[string]int{"variant": 29, "closure": 10, "collision": 8}
	if !reflect.DeepEqual(counts, want) {
		t.Fatal(fmt.Errorf("corpus counts = %v, want %v", counts, want))
	}
	for _, name := range []string{"baseline-directory", "raw-false-zero", "nonretained-payload", "closure-diamond", "closure-cycle", "closure-edge-before-visited", "collision-identical", "collision-unselected"} {
		if !names[name] {
			t.Fatal(errors.New("required fixture missing: " + name))
		}
	}
}
