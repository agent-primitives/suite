package agentsuite_test

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"os/exec"
	"reflect"
	"strings"
	"testing"

	"github.com/agent-primitives/suite/core"
)

func TestCorePortableTypes(t *testing.T) {
	// Reflection reports the canonical defining package after the split.
	for _, typ := range []reflect.Type{
		reflect.TypeFor[core.Agent](),
		reflect.TypeFor[core.AgentInvoke](),
		reflect.TypeFor[core.AgentPlatform](),
		reflect.TypeFor[core.BrokeredCredential](),
		reflect.TypeFor[core.BuildProfile](),
		reflect.TypeFor[core.Composition](),
		reflect.TypeFor[core.CompositionRef](),
		reflect.TypeFor[core.CompositionSelection](),
		reflect.TypeFor[core.DelegatedAuthorization](),
		reflect.TypeFor[core.Descriptor](),
		reflect.TypeFor[core.EnvironmentName](),
		reflect.TypeFor[core.EvaluationAssertion](),
		reflect.TypeFor[core.EvaluationCase](),
		reflect.TypeFor[core.EvaluationIndex](),
		reflect.TypeFor[core.EvaluationLimits](),
		reflect.TypeFor[core.EvidenceImplementation](),
		reflect.TypeFor[core.ExecutionContract](),
		reflect.TypeFor[core.ExecutionInput](),
		reflect.TypeFor[core.Extension](),
		reflect.TypeFor[core.FileRef](),
		reflect.TypeFor[core.InferenceRequirements](),
		reflect.TypeFor[core.InventoryEntry](),
		reflect.TypeFor[core.ManifestRef](),
		reflect.TypeFor[core.ModelRequirement](),
		reflect.TypeFor[core.NetworkAccess](),
		reflect.TypeFor[core.Platform](),
		reflect.TypeFor[core.PlatformImage](),
		reflect.TypeFor[core.RemoteHeader](),
		reflect.TypeFor[core.RemoteNetworkRequirement](),
		reflect.TypeFor[core.RemoteTimeouts](),
		reflect.TypeFor[core.RemoteToolProvider](),
		reflect.TypeFor[core.Report](),
		reflect.TypeFor[core.ResolvedToolProvider](),
		reflect.TypeFor[core.RuntimeProfile](),
		reflect.TypeFor[core.RuntimeRequirement](),
		reflect.TypeFor[core.SecretKeyRef](),
		reflect.TypeFor[core.Suite](),
		reflect.TypeFor[core.Tool](),
		reflect.TypeFor[core.ToolProvider](),
		reflect.TypeFor[core.ToolProviderCatalog](),
		reflect.TypeFor[core.ToolProviderComposition](),
		reflect.TypeFor[core.ToolProviderCompositionRef](),
		reflect.TypeFor[core.ToolProviderDependency](),
		reflect.TypeFor[core.ToolProviderRequirement](),
		reflect.TypeFor[core.ToolProviderVariant](),
	} {
		if typ.PkgPath() != "github.com/agent-primitives/suite/core" {
			t.Errorf("%s: defining package changed to %s", typ.Name(), typ.PkgPath())
		}
	}
	// Supported helpers and JSON methods keep their signatures.
	var _ func(any) ([]byte, error) = core.Marshal
	var _ func([]byte, any) error = core.Unmarshal
	var _ func([]byte) (string, error) = core.Digest
	var _ func([]byte, core.Descriptor) bool = core.DescriptorSizeAndDigestMatch
	var _ func([]byte, core.Descriptor) bool = core.MatchesCanonicalDescriptor
	var _ func(string) bool = core.IsValidDigest
	var _ func(string) error = core.ValidateImageReference
	var _ func(core.ExecutionContract) error = core.ValidateExecutionContract
	var _ json.Unmarshaler = (*core.RuntimeProfile)(nil)
	var _ json.Unmarshaler = (*core.Suite)(nil)
	var _ json.Unmarshaler = (*core.Composition)(nil)
	var _ json.Unmarshaler = (*core.CompositionRef)(nil)
}

func TestCoreJSONAndIdentity(t *testing.T) {
	digest := "sha256:" + strings.Repeat("a", 64)
	implementation := core.EvidenceImplementation{ID: "native", Version: "1.0.0", Digest: digest}
	profile := core.RuntimeProfile{SchemaVersion: core.SpecVersion, MediaType: core.MediaTypeRuntimeProfile, ID: "native", Runtime: implementation, Harness: implementation, Renderer: implementation, ConfigurationABI: "native-v1", ImageRequired: false}
	raw, err := core.Marshal(profile)
	if err != nil {
		t.Fatal(err)
	}
	// Hand-ordered JCS fields pin the stored JSON contract, including false.
	identity := `{"digest":"` + digest + `","id":"native","version":"1.0.0"}`
	want := `{"configurationABI":"native-v1","harness":` + identity + `,"id":"native","imageRequired":false,"mediaType":"application/vnd.agentsuite.runtime.profile.v1+json","renderer":` + identity + `,"runtime":` + identity + `,"schemaVersion":"1.0.0-draft"}`
	if string(raw) != want {
		t.Fatalf("canonical runtime profile: %s; want %s", raw, want)
	}
	var decoded core.RuntimeProfile
	if err := core.Unmarshal(raw, &decoded); err != nil || decoded != profile {
		t.Fatalf("core decode: %#v %v", decoded, err)
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
				var value core.RuntimeProfile
				if err := core.Unmarshal(input, &value); err == nil {
					t.Fatalf("accepted required field %s missing/null (null=%v)", key, null)
				}
			}
		})
	}
	gotDigest, err := core.Digest(raw)
	wantDigest := fmt.Sprintf("sha256:%x", sha256.Sum256([]byte(want)))
	if err != nil || gotDigest != wantDigest {
		t.Fatalf("digest: %s; want %s; error: %v", gotDigest, wantDigest, err)
	}
	descriptor := core.Descriptor{MediaType: core.MediaTypeRuntimeProfile, Digest: wantDigest, Size: int64(len(want))}
	if !core.DescriptorSizeAndDigestMatch(raw, descriptor) || !core.MatchesCanonicalDescriptor(raw, descriptor) {
		t.Fatal("descriptor lost canonical identity")
	}
}

// The module root is documentation-only; no alias, value or forwarder may
// silently keep the removed API usable.
func TestRootHasNoExports(t *testing.T) {
	entries, err := os.ReadDir(".")
	if err != nil {
		t.Fatal(err)
	}
	var exports []string
	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".go") || strings.HasSuffix(entry.Name(), "_test.go") {
			continue
		}
		file, err := parser.ParseFile(token.NewFileSet(), entry.Name(), nil, 0)
		if err != nil {
			t.Fatal(err)
		}
		for _, declaration := range file.Decls {
			switch declaration := declaration.(type) {
			case *ast.FuncDecl:
				if declaration.Recv == nil && ast.IsExported(declaration.Name.Name) {
					exports = append(exports, declaration.Name.Name)
				}
			case *ast.GenDecl:
				for _, spec := range declaration.Specs {
					switch spec := spec.(type) {
					case *ast.TypeSpec:
						if ast.IsExported(spec.Name.Name) {
							exports = append(exports, spec.Name.Name)
						}
					case *ast.ValueSpec:
						for _, name := range spec.Names {
							if ast.IsExported(name.Name) {
								exports = append(exports, name.Name)
							}
						}
					}
				}
			}
		}
	}
	if len(exports) != 0 {
		t.Fatalf("root must export nothing; found %d exports: %v", len(exports), exports)
	}
}

func TestCoreDependencies(t *testing.T) {
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
