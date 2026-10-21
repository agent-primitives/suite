package agentsuite_test

import (
	"bytes"
	"encoding/json"
	"go/ast"
	"go/doc/comment"
	"go/parser"
	"go/token"
	"os"
	"os/exec"
	"reflect"
	"strings"
	"testing"

	agentsuite "github.com/agent-primitives/suite"
	"github.com/agent-primitives/suite/core"
)

func TestCoreCompatibilityTypes(t *testing.T) {
	pairs := []struct {
		name       string
		root, core reflect.Type
	}{
		{"Agent", reflect.TypeFor[agentsuite.Agent](), reflect.TypeFor[core.Agent]()},
		{"AgentInvoke", reflect.TypeFor[agentsuite.AgentInvoke](), reflect.TypeFor[core.AgentInvoke]()},
		{"AgentPlatform", reflect.TypeFor[agentsuite.AgentPlatform](), reflect.TypeFor[core.AgentPlatform]()},
		{"BrokeredCredential", reflect.TypeFor[agentsuite.BrokeredCredential](), reflect.TypeFor[core.BrokeredCredential]()},
		{"BuildProfile", reflect.TypeFor[agentsuite.BuildProfile](), reflect.TypeFor[core.BuildProfile]()},
		{"Composition", reflect.TypeFor[agentsuite.Composition](), reflect.TypeFor[core.Composition]()},
		{"CompositionRef", reflect.TypeFor[agentsuite.CompositionRef](), reflect.TypeFor[core.CompositionRef]()},
		{"CompositionSelection", reflect.TypeFor[agentsuite.CompositionSelection](), reflect.TypeFor[core.CompositionSelection]()},
		{"DelegatedAuthorization", reflect.TypeFor[agentsuite.DelegatedAuthorization](), reflect.TypeFor[core.DelegatedAuthorization]()},
		{"Descriptor", reflect.TypeFor[agentsuite.Descriptor](), reflect.TypeFor[core.Descriptor]()},
		{"EnvironmentName", reflect.TypeFor[agentsuite.EnvironmentName](), reflect.TypeFor[core.EnvironmentName]()},
		{"EvaluationAssertion", reflect.TypeFor[agentsuite.EvaluationAssertion](), reflect.TypeFor[core.EvaluationAssertion]()},
		{"EvaluationCase", reflect.TypeFor[agentsuite.EvaluationCase](), reflect.TypeFor[core.EvaluationCase]()},
		{"EvaluationIndex", reflect.TypeFor[agentsuite.EvaluationIndex](), reflect.TypeFor[core.EvaluationIndex]()},
		{"EvaluationLimits", reflect.TypeFor[agentsuite.EvaluationLimits](), reflect.TypeFor[core.EvaluationLimits]()},
		{"EvidenceImplementation", reflect.TypeFor[agentsuite.EvidenceImplementation](), reflect.TypeFor[core.EvidenceImplementation]()},
		{"ExecutionContract", reflect.TypeFor[agentsuite.ExecutionContract](), reflect.TypeFor[core.ExecutionContract]()},
		{"ExecutionInput", reflect.TypeFor[agentsuite.ExecutionInput](), reflect.TypeFor[core.ExecutionInput]()},
		{"Extension", reflect.TypeFor[agentsuite.Extension](), reflect.TypeFor[core.Extension]()},
		{"FileRef", reflect.TypeFor[agentsuite.FileRef](), reflect.TypeFor[core.FileRef]()},
		{"InferenceRequirements", reflect.TypeFor[agentsuite.InferenceRequirements](), reflect.TypeFor[core.InferenceRequirements]()},
		{"InventoryEntry", reflect.TypeFor[agentsuite.InventoryEntry](), reflect.TypeFor[core.InventoryEntry]()},
		{"ManifestRef", reflect.TypeFor[agentsuite.ManifestRef](), reflect.TypeFor[core.ManifestRef]()},
		{"ModelRequirement", reflect.TypeFor[agentsuite.ModelRequirement](), reflect.TypeFor[core.ModelRequirement]()},
		{"NetworkAccess", reflect.TypeFor[agentsuite.NetworkAccess](), reflect.TypeFor[core.NetworkAccess]()},
		{"Platform", reflect.TypeFor[agentsuite.Platform](), reflect.TypeFor[core.Platform]()},
		{"PlatformImage", reflect.TypeFor[agentsuite.PlatformImage](), reflect.TypeFor[core.PlatformImage]()},
		{"RemoteHeader", reflect.TypeFor[agentsuite.RemoteHeader](), reflect.TypeFor[core.RemoteHeader]()},
		{"RemoteNetworkRequirement", reflect.TypeFor[agentsuite.RemoteNetworkRequirement](), reflect.TypeFor[core.RemoteNetworkRequirement]()},
		{"RemoteTimeouts", reflect.TypeFor[agentsuite.RemoteTimeouts](), reflect.TypeFor[core.RemoteTimeouts]()},
		{"RemoteToolProvider", reflect.TypeFor[agentsuite.RemoteToolProvider](), reflect.TypeFor[core.RemoteToolProvider]()},
		{"Report", reflect.TypeFor[agentsuite.Report](), reflect.TypeFor[core.Report]()},
		{"ResolvedToolProvider", reflect.TypeFor[agentsuite.ResolvedToolProvider](), reflect.TypeFor[core.ResolvedToolProvider]()},
		{"RuntimeProfile", reflect.TypeFor[agentsuite.RuntimeProfile](), reflect.TypeFor[core.RuntimeProfile]()},
		{"RuntimeRequirement", reflect.TypeFor[agentsuite.RuntimeRequirement](), reflect.TypeFor[core.RuntimeRequirement]()},
		{"SecretKeyRef", reflect.TypeFor[agentsuite.SecretKeyRef](), reflect.TypeFor[core.SecretKeyRef]()},
		{"Suite", reflect.TypeFor[agentsuite.Suite](), reflect.TypeFor[core.Suite]()},
		{"Tool", reflect.TypeFor[agentsuite.Tool](), reflect.TypeFor[core.Tool]()},
		{"ToolProvider", reflect.TypeFor[agentsuite.ToolProvider](), reflect.TypeFor[core.ToolProvider]()},
		{"ToolProviderCatalog", reflect.TypeFor[agentsuite.ToolProviderCatalog](), reflect.TypeFor[core.ToolProviderCatalog]()},
		{"ToolProviderComposition", reflect.TypeFor[agentsuite.ToolProviderComposition](), reflect.TypeFor[core.ToolProviderComposition]()},
		{"ToolProviderCompositionRef", reflect.TypeFor[agentsuite.ToolProviderCompositionRef](), reflect.TypeFor[core.ToolProviderCompositionRef]()},
		{"ToolProviderDependency", reflect.TypeFor[agentsuite.ToolProviderDependency](), reflect.TypeFor[core.ToolProviderDependency]()},
		{"ToolProviderRequirement", reflect.TypeFor[agentsuite.ToolProviderRequirement](), reflect.TypeFor[core.ToolProviderRequirement]()},
		{"ToolProviderVariant", reflect.TypeFor[agentsuite.ToolProviderVariant](), reflect.TypeFor[core.ToolProviderVariant]()},
	}
	for _, p := range pairs {
		if p.root != p.core {
			t.Errorf("%s is not a type alias: %v != %v", p.name, p.root, p.core)
		}
	}
	if agentsuite.AgentKitMountedConfig != core.AgentKitMountedConfig {
		t.Error("AgentKitMountedConfig changed")
	}
	if agentsuite.ExecutionHTTPV1 != core.ExecutionHTTPV1 {
		t.Error("ExecutionHTTPV1 changed")
	}
	if agentsuite.ExecutionSharedSandbox != core.ExecutionSharedSandbox {
		t.Error("ExecutionSharedSandbox changed")
	}
	if agentsuite.LayoutVersion != core.LayoutVersion {
		t.Error("LayoutVersion changed")
	}
	if agentsuite.MediaTypeAgent != core.MediaTypeAgent {
		t.Error("MediaTypeAgent changed")
	}
	if agentsuite.MediaTypeArtifact != core.MediaTypeArtifact {
		t.Error("MediaTypeArtifact changed")
	}
	if agentsuite.MediaTypeBuildProfile != core.MediaTypeBuildProfile {
		t.Error("MediaTypeBuildProfile changed")
	}
	if agentsuite.MediaTypeComposition != core.MediaTypeComposition {
		t.Error("MediaTypeComposition changed")
	}
	if agentsuite.MediaTypeContent != core.MediaTypeContent {
		t.Error("MediaTypeContent changed")
	}
	if agentsuite.MediaTypeEmptyConfig != core.MediaTypeEmptyConfig {
		t.Error("MediaTypeEmptyConfig changed")
	}
	if agentsuite.MediaTypeEvaluationCase != core.MediaTypeEvaluationCase {
		t.Error("MediaTypeEvaluationCase changed")
	}
	if agentsuite.MediaTypeEvaluationIndex != core.MediaTypeEvaluationIndex {
		t.Error("MediaTypeEvaluationIndex changed")
	}
	if agentsuite.MediaTypeInstructions != core.MediaTypeInstructions {
		t.Error("MediaTypeInstructions changed")
	}
	if agentsuite.MediaTypeJSONSchema != core.MediaTypeJSONSchema {
		t.Error("MediaTypeJSONSchema changed")
	}
	if agentsuite.MediaTypePolicyV1 != core.MediaTypePolicyV1 {
		t.Error("MediaTypePolicyV1 changed")
	}
	if agentsuite.MediaTypePolicyV2 != core.MediaTypePolicyV2 {
		t.Error("MediaTypePolicyV2 changed")
	}
	if agentsuite.MediaTypeRuntimeProfile != core.MediaTypeRuntimeProfile {
		t.Error("MediaTypeRuntimeProfile changed")
	}
	if agentsuite.MediaTypeSuite != core.MediaTypeSuite {
		t.Error("MediaTypeSuite changed")
	}
	if agentsuite.MediaTypeToolProvider != core.MediaTypeToolProvider {
		t.Error("MediaTypeToolProvider changed")
	}
	if agentsuite.MediaTypeToolProviderCatalog != core.MediaTypeToolProviderCatalog {
		t.Error("MediaTypeToolProviderCatalog changed")
	}
	if agentsuite.MediaTypeToolProviderComposition != core.MediaTypeToolProviderComposition {
		t.Error("MediaTypeToolProviderComposition changed")
	}
	if agentsuite.SpecVersion != core.SpecVersion {
		t.Error("SpecVersion changed")
	}
	// These assignments reject signature changes and wrapper types at compile time.
	var _ func(any) ([]byte, error) = core.Marshal
	var _ func([]byte, any) error = core.Unmarshal
	var _ func([]byte) (string, error) = core.Digest
	var _ func([]byte, agentsuite.Descriptor) bool = core.DescriptorSizeAndDigestMatch
	var _ func([]byte, agentsuite.Descriptor) bool = core.MatchesCanonicalDescriptor
	var _ func(string) bool = core.IsValidDigest
	var _ func(string) error = core.ValidateImageReference
	var _ func(agentsuite.ExecutionContract) error = core.ValidateExecutionContract
	var _ agentsuite.EvidenceImplementation = core.RuntimeProfile{}.Runtime
	var _ core.EvidenceImplementation = agentsuite.RuntimeProfile{}.Runtime
}

func TestCoreCompatibilityJSON(t *testing.T) {
	digest := "sha256:" + strings.Repeat("a", 64)
	implementation := core.EvidenceImplementation{ID: "native", Version: "1.0.0", Digest: digest}
	profile := core.RuntimeProfile{SchemaVersion: core.SpecVersion, MediaType: core.MediaTypeRuntimeProfile, ID: "native", Runtime: implementation, Harness: implementation, Renderer: implementation, ConfigurationABI: "native-v1", ImageRequired: false}
	raw, err := core.Marshal(profile)
	if err != nil {
		t.Fatal(err)
	}
	rootRaw, err := agentsuite.Marshal(profile)
	if err != nil || !bytes.Equal(raw, rootRaw) {
		t.Fatalf("marshal differs: %s %s %v", raw, rootRaw, err)
	}
	var old agentsuite.RuntimeProfile
	if err := agentsuite.Unmarshal(raw, &old); err != nil || old != profile {
		t.Fatalf("root decode: %#v %v", old, err)
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(raw, &fields); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"runtime", "imageRequired", "configurationABI"} {
		t.Run(key, func(t *testing.T) {
			saved := fields[key]
			defer func() { fields[key] = saved }()
			for _, null := range []bool{false, true} {
				if null {
					fields[key] = json.RawMessage("null")
				} else {
					delete(fields, key)
				}
				input, err := json.Marshal(fields)
				if err != nil {
					t.Fatal(err)
				}
				var a agentsuite.RuntimeProfile
				var b core.RuntimeProfile
				ea, eb := agentsuite.Unmarshal(input, &a), core.Unmarshal(input, &b)
				if ea == nil || eb == nil || ea.Error() != eb.Error() {
					t.Fatalf("required/null refusal differs: %v / %v", ea, eb)
				}
			}
		})
	}
	left, err := agentsuite.Digest(raw)
	if err != nil {
		t.Fatal(err)
	}
	right, err := core.Digest(raw)
	if err != nil || left != right {
		t.Fatalf("digest differs: %s / %s %v", left, right, err)
	}
	descriptor := agentsuite.Descriptor{MediaType: core.MediaTypeRuntimeProfile, Digest: left, Size: int64(len(raw))}
	if !core.DescriptorSizeAndDigestMatch(raw, descriptor) || !agentsuite.MatchesCanonicalDescriptor(raw, descriptor) {
		t.Fatal("descriptor alias lost canonical identity")
	}
}

// Go tooling recognises Deprecated only at the start of a separate paragraph.
func TestCoreCompatibilityDeprecations(t *testing.T) {
	entries, err := os.ReadDir(".")
	if err != nil {
		t.Fatal(err)
	}
	var parsed comment.Parser
	aliases, forwarders, constants, deprecations := 0, 0, 0, 0
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".go") || strings.HasSuffix(entry.Name(), "_test.go") {
			continue
		}
		file, err := parser.ParseFile(token.NewFileSet(), entry.Name(), nil, parser.ParseComments)
		if err != nil {
			t.Fatal(err)
		}
		for _, group := range file.Comments {
			for _, block := range parsed.Parse(group.Text()).Content {
				paragraph, ok := block.(*comment.Paragraph)
				if !ok {
					continue
				}
				var plain strings.Builder
				for _, part := range paragraph.Text {
					if text, ok := part.(comment.Plain); ok {
						plain.WriteString(string(text))
					}
				}
				note := plain.String()
				if !strings.HasPrefix(note, "Deprecated:") {
					continue
				}
				deprecations++
				if group != file.Doc {
					t.Errorf("%s: deprecation must be in the package documentation", entry.Name())
				}
				for _, want := range []string{
					"github.com/agent-primitives/suite/core",
					"github.com/agent-primitives/suite/oci",
					"github.com/agent-primitives/suite/evidence",
					"github.com/agent-primitives/suite/experimental/flow",
					"v0.7.x", "v0.8.0",
				} {
					if !strings.Contains(note, want) {
						t.Errorf("package deprecation does not explain %q", want)
					}
				}
			}
		}
		for _, declaration := range file.Decls {
			if function, ok := declaration.(*ast.FuncDecl); ok && ast.IsExported(function.Name.Name) {
				forwarders++
			}
			decl, ok := declaration.(*ast.GenDecl)
			if !ok {
				continue
			}
			for _, spec := range decl.Specs {
				switch spec := spec.(type) {
				case *ast.TypeSpec:
					if ast.IsExported(spec.Name.Name) {
						if !spec.Assign.IsValid() {
							t.Errorf("%s must remain a true alias", spec.Name.Name)
						}
						aliases++
					}
				case *ast.ValueSpec:
					if decl.Tok == token.CONST {
						for _, name := range spec.Names {
							if ast.IsExported(name.Name) {
								constants++
							}
						}
					}
				}
			}
		}
	}
	if deprecations != 1 {
		t.Errorf("want one package deprecation, got %d", deprecations)
	}
	if aliases != 79 || forwarders != 15 || constants != 35 {
		t.Fatalf("compatibility coverage: %d aliases, %d forwarders, %d constants; want 79, 15, 35", aliases, forwarders, constants)
	}
}

func TestCoreCompatibilityDependencies(t *testing.T) {
	command := exec.Command("go", "list", "-deps", "github.com/agent-primitives/suite/core")
	output, err := command.CombinedOutput()
	if err != nil {
		t.Fatalf("core dependencies: %v\n%s", err, output)
	}
	for _, dep := range strings.Fields(string(output)) {
		if dep == "github.com/agent-primitives/suite" || strings.HasPrefix(dep, "github.com/agent-primitives/suite/internal/artifact") || strings.HasPrefix(dep, "github.com/agent-primitives/suite/evidence") || strings.HasPrefix(dep, "github.com/agent-primitives/suite/experimental") || strings.HasPrefix(dep, "github.com/agent-primitives/suite/oci") {
			t.Errorf("core imports heavy package %s", dep)
		}
	}
}
