package artifact

import (
	"bytes"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/gowebpki/jcs"
)

const richEvaluationRoot = "../../testdata/rich-evaluations"

// This vector is separate from the package: golden metadata is not package content.
// The package row uses the shared conformance corpus's directory-row shape.
type richEvaluationGolden struct {
	Package struct {
		Name           string `json:"name"`
		Path           string `json:"path"`
		Form           string `json:"form"`
		ContentDigest  string `json:"contentDigest"`
		RootDigest     string `json:"rootDigest"`
		ManifestDigest string `json:"manifestDigest"`
		Valid          bool   `json:"valid"`
	} `json:"package"`
	Documents []struct {
		Path       string     `json:"path"`
		Schema     string     `json:"schema"`
		Descriptor Descriptor `json:"descriptor"`
	} `json:"documents"`
}

func readRichEvaluationGolden(t *testing.T) richEvaluationGolden {
	t.Helper()
	var golden richEvaluationGolden
	readStrictJSON(t, "../../testdata/rich-evaluations.golden.json", &golden)
	if golden.Package.Name != "rich-evaluations" || golden.Package.Path != "rich-evaluations" ||
		golden.Package.Form != "directory" || !golden.Package.Valid || golden.Package.ManifestDigest != "" || len(golden.Documents) != 15 {
		t.Fatalf("incomplete fixture vector: %+v", golden)
	}
	shared := packageConformanceNamed(t, golden.Package.Name)
	if shared.Path != "../"+golden.Package.Path || shared.Form != golden.Package.Form || shared.Valid != golden.Package.Valid ||
		shared.ContentDigest != golden.Package.ContentDigest || shared.RootDigest != golden.Package.RootDigest || shared.ManifestDigest != golden.Package.ManifestDigest {
		t.Fatalf("shared corpus disagrees with fixture vector: %+v", shared)
	}
	return golden
}

func copyRichEvaluationFixture(t *testing.T) string {
	t.Helper()
	root := copyAgentSuiteDirectory(t, richEvaluationRoot)
	secureDirectoryFixture(t, root)
	return root
}

func TestRichEvaluationFixtureConformance(t *testing.T) {
	root := copyRichEvaluationFixture(t)
	report, err := ValidateDirectory(root)
	if err != nil {
		t.Fatal(err)
	}
	if report.Name != "rich-evaluations" || report.Agents != 1 || report.ToolProviders != 1 || report.Compositions != 1 {
		t.Fatalf("unexpected graph: %+v", report)
	}

	golden := readRichEvaluationGolden(t)
	seen := map[string]bool{}
	for _, document := range golden.Documents {
		t.Run(document.Path, func(t *testing.T) {
			if seen[document.Path] {
				t.Fatalf("duplicate golden path %s", document.Path)
			}
			seen[document.Path] = true
			data, err := os.ReadFile(filepath.Join(root, document.Path))
			if err != nil {
				t.Fatal(err)
			}
			if document.Schema != "" {
				validateSchemaJSON(t, compileReferenceSchema(t, document.Schema), string(data), true)
			}
			if strings.HasSuffix(document.Path, ".json") {
				canonical, err := jcs.Transform(data)
				if err != nil {
					t.Fatal(err)
				}
				if !bytes.Equal(data, canonical) {
					t.Fatal("fixture JSON is not stored as canonical bytes")
				}
				gotDigest, err := canonicalDigest(data)
				if err != nil {
					t.Fatal(err)
				}
				gotSize, err := canonicalSize(data)
				if err != nil {
					t.Fatal(err)
				}
				if gotDigest != document.Descriptor.Digest || gotSize != document.Descriptor.Size {
					t.Fatalf("canonical identity = %s/%d, want %+v", gotDigest, gotSize, document.Descriptor)
				}
			}
			if got := digestBytes(data); got != document.Descriptor.Digest || int64(len(data)) != document.Descriptor.Size {
				t.Fatalf("identity = %s/%d, want %+v", got, len(data), document.Descriptor)
			}
		})
	}
	// A new file must not silently escape the golden inventory.
	if err := filepath.WalkDir(root, func(name string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if !entry.IsDir() {
			relative, err := filepath.Rel(root, name)
			if err != nil {
				return err
			}
			if !seen[filepath.ToSlash(relative)] {
				t.Errorf("file missing from golden inventory: %s", relative)
			}
		}
		return nil
	}); err != nil {
		t.Fatal(err)
	}
	identity, err := DiffPaths(root, root)
	if err != nil {
		t.Fatal(err)
	}
	if identity.Before.ContentDigest != golden.Package.ContentDigest || identity.HasChanges() {
		t.Fatalf("content identity = %s, want %s", identity.Before.ContentDigest, golden.Package.ContentDigest)
	}
	if golden.Documents[0].Path != "agentsuite.json" || golden.Documents[0].Descriptor.Digest != golden.Package.RootDigest {
		t.Fatal("root identity disagrees with document vector")
	}
}

func TestRichEvaluationFixtureOrderedConstraints(t *testing.T) {
	root := copyRichEvaluationFixture(t)
	content, err := loadDirectory(root)
	if err != nil {
		t.Fatal(err)
	}
	graph, _, err := validateContentGraph(content)
	if err != nil {
		t.Fatal(err)
	}
	golden := readRichEvaluationGolden(t)
	pins := map[string]Descriptor{}
	for _, document := range golden.Documents {
		pins[document.Path] = document.Descriptor
	}
	agent := graph.agents["writer"]
	if len(agent.Evals) != 1 || agent.Evals[0].Path != "evals/writer/index.json" || !reflect.DeepEqual(agent.Evals[0].Descriptor, pins[agent.Evals[0].Path]) {
		t.Fatalf("evaluation source = %+v", agent.Evals)
	}
	if agent.Policy == nil || agent.Policy.Path != "policies/writer.json" || !reflect.DeepEqual(agent.Policy.Descriptor, pins[agent.Policy.Path]) {
		t.Fatalf("policy source = %+v", agent.Policy)
	}
	providerRef := graph.suite.ToolProviderCatalog
	var catalog ToolProviderCatalog
	readStrictJSON(t, filepath.Join(root, providerRef.Path), &catalog)
	if len(catalog.ToolProviders) != 1 || catalog.ToolProviders[0].Path != "tool-providers/lookup/1.0.0/tool-provider.json" || !reflect.DeepEqual(catalog.ToolProviders[0].Descriptor, pins[catalog.ToolProviders[0].Path]) {
		t.Fatalf("provider source = %+v", catalog.ToolProviders)
	}
	provider := graph.toolProviders["lookup@1.0.0"]
	if len(provider.Tools) != 1 || provider.Tools[0].Name != "lookup" || !reflect.DeepEqual(provider.Tools[0].InputSchema.Descriptor, pins["schemas/lookup-input.json"]) {
		t.Fatalf("callable tool = %+v", provider.Tools)
	}
	var index EvaluationIndex
	readStrictJSON(t, filepath.Join(root, agent.Evals[0].Path), &index)
	three, two, threshold, noncritical := 3, 2, 85, false
	// Operands are constraints, not reference answers. Literal expectations catch
	// decoding that drops pins, optional false, repeat policy or array ordering.
	want := []EvaluationCase{
		{SchemaVersion: SpecVersion, MediaType: MediaTypeEvaluationCase, ID: "retrieve", Input: "Find a source about migrating a package and cite its identifier.", Assertions: []EvaluationAssertion{
			{ID: "lookup-used", Type: "toolCalled", Tool: "lookup"},
			{ID: "citation", Type: "contains", Value: "source:"},
		}},
		{SchemaVersion: SpecVersion, MediaType: MediaTypeEvaluationCase, ID: "summarize", Input: "Summarize the supplied migration notes without inventing facts.", Runs: &three, MinPasses: &two, Assertions: []EvaluationAssertion{
			{ID: "grounded", Type: "llmJudge", Rubric: "The summary preserves the supplied facts, distinguishes uncertainty and invents no migration steps.", MinScore: &threshold, JudgeModel: "example-judge", JudgeVersion: "2026-01-15"},
			{ID: "no-guarantee", Type: "notContains", Value: "guaranteed", Critical: &noncritical},
		}},
		{SchemaVersion: SpecVersion, MediaType: MediaTypeEvaluationCase, ID: "format", Input: "Return a source citation on its own line, using a lowercase source identifier.", Runs: &two, Assertions: []EvaluationAssertion{
			{ID: "citation-format", Type: "regex", Pattern: `(?m)^source: [a-z0-9-]+$`},
		}},
		{SchemaVersion: SpecVersion, MediaType: MediaTypeEvaluationCase, ID: "offline", Input: "Explain how to inspect a local package offline. Do not look up external sources.", Assertions: []EvaluationAssertion{
			{ID: "no-lookup", Type: "toolNotCalled", Tool: "lookup"},
			{ID: "offline-scope", Type: "contains", Value: "offline"},
		}},
	}
	if len(index.Cases) != len(want) {
		t.Fatalf("case count = %d, want %d", len(index.Cases), len(want))
	}
	for i, expected := range want {
		ref := index.Cases[i]
		if ref.Path != "evals/writer/cases/"+expected.ID+".json" || !reflect.DeepEqual(ref.Descriptor, pins[ref.Path]) {
			t.Fatalf("case %d source = %+v", i, ref)
		}
		var got EvaluationCase
		readStrictJSON(t, filepath.Join(root, ref.Path), &got)
		if !reflect.DeepEqual(got, expected) {
			t.Errorf("%s constraints = %+v, want %+v", ref.Path, got, expected)
		}
	}
}

func TestRichEvaluationFixtureRejectsStaleSources(t *testing.T) {
	for _, tc := range []struct {
		name, path, before, after, want string
	}{
		{"judge threshold", "evals/writer/cases/summarize.json", `"minScore":85`, `"minScore":86`, "evaluation document digest mismatch"},
		{"repeat policy", "evals/writer/cases/summarize.json", `"minPasses":2`, `"minPasses":3`, "evaluation document digest mismatch"},
		{"provider contract", "tool-providers/lookup/1.0.0/tool-provider.json", `"name":"lookup"`, `"name":"other"`, "digest mismatch"},
		{"policy", "policies/writer.json", `"port":443`, `"port":444`, "digest mismatch"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			root := copyRichEvaluationFixture(t)
			data, err := os.ReadFile(filepath.Join(root, tc.path))
			if err != nil {
				t.Fatal(err)
			}
			changed := bytes.Replace(data, []byte(tc.before), []byte(tc.after), 1)
			if bytes.Equal(data, changed) {
				t.Fatal("mutation did not change fixture")
			}
			mustWrite(t, root, tc.path, changed)
			if _, err := ValidateDirectory(root); err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("stale source: %v, want %q", err, tc.want)
			}
		})
	}
}

func TestRichEvaluationFixtureOrderChangesIdentity(t *testing.T) {
	for _, order := range []string{"cases", "assertions"} {
		t.Run(order, func(t *testing.T) {
			root := copyRichEvaluationFixture(t)
			var agent Agent
			readStrictJSON(t, filepath.Join(root, "agents/writer.json"), &agent)
			ref := agent.Evals[0]
			var index EvaluationIndex
			readStrictJSON(t, filepath.Join(root, ref.Path), &index)
			if order == "cases" {
				index.Cases[0], index.Cases[1] = index.Cases[1], index.Cases[0]
			} else {
				caseRef := &index.Cases[0]
				var c EvaluationCase
				readStrictJSON(t, filepath.Join(root, caseRef.Path), &c)
				c.Assertions[0], c.Assertions[1] = c.Assertions[1], c.Assertions[0]
				caseRef.Descriptor = mustWriteJSON(t, root, caseRef.Path, MediaTypeEvaluationCase, c)
			}
			ref.Descriptor = mustWriteJSON(t, root, ref.Path, MediaTypeEvaluationIndex, index)
			if _, err := ValidateDirectory(root); err == nil || !strings.Contains(err.Error(), "digest mismatch") {
				t.Fatalf("stale ordered index: %v", err)
			}
			bindEvaluationAgent(t, root, []FileRef{ref})
			if _, err := ValidateDirectory(root); err != nil {
				t.Fatalf("rebound ordered index: %v", err)
			}
			identity, err := DiffPaths(copyRichEvaluationFixture(t), root)
			if err != nil {
				t.Fatal(err)
			}
			golden := readRichEvaluationGolden(t)
			if identity.Before.ContentDigest != golden.Package.ContentDigest || identity.Before.ContentDigest == identity.After.ContentDigest || !identity.HasChanges() {
				t.Fatalf("%s order did not propagate identity: %+v", order, identity)
			}
		})
	}
}
