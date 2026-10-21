package artifact

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func writeFlowSuite(t *testing.T) string {
	t.Helper()
	root, _ := writeEvaluationSuite(t, nil)
	var suite Suite
	readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
	var reviewer Agent
	readStrictJSON(t, filepath.Join(root, suite.Agents[0].Path), &reviewer)
	reviewer.ID, reviewer.Evals = "reviewer", nil
	path := "agents/reviewer.json"
	suite.Agents = append(suite.Agents, ManifestRef{ID: "reviewer", Path: path, Descriptor: mustWriteJSON(t, root, path, MediaTypeAgent, reviewer)})
	var composition Composition
	readStrictJSON(t, filepath.Join(root, suite.Compositions[0].Path), &composition)
	composition.Agent = "reviewer"
	path = "compositions/reviewer-linux-amd64.json"
	suite.Compositions = append(suite.Compositions, CompositionRef{Agent: "reviewer", Platform: composition.Platform, Path: path, Descriptor: mustWriteJSON(t, root, path, MediaTypeComposition, composition)})
	raw, err := os.ReadFile("../../testdata/flow-v1alpha1/flow.json")
	if err != nil {
		t.Fatal(err)
	}
	mustWrite(t, root, "coordination/flow.json", raw)
	suite.Extensions = append(suite.Extensions, Extension{Name: "kmx.flow.v1alpha1", Critical: true, Digest: digestBytes(raw)})
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
	return root
}

func rewriteFlow(t *testing.T, root string, mutate func(*FlowV1Alpha1)) {
	t.Helper()
	var flow FlowV1Alpha1
	readStrictJSON(t, filepath.Join(root, "coordination/flow.json"), &flow)
	mutate(&flow)
	raw, err := Marshal(flow)
	if err != nil {
		t.Fatal(err)
	}
	mustWrite(t, root, "coordination/flow.json", raw)
	var suite Suite
	readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
	suite.Extensions[len(suite.Extensions)-1].Digest = digestBytes(raw)
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
}

func TestFlowV1Alpha1OriginalGraphAndStrictRefusal(t *testing.T) {
	root := writeFlowSuite(t)
	for _, validate := range []func(string) (*Report, error){ValidateDirectory, ValidatePath} {
		if _, err := validate(root); err == nil {
			t.Fatal("strict reader accepted required experimental flow")
		}
	}
	graph, err := ValidateDirectoryFlowV1Alpha1(root)
	if err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(filepath.Join(root, "coordination/flow.json"))
	if err != nil {
		t.Fatal(err)
	}
	if graph.FlowDigest() != digestBytes(raw) || graph.Report().Agents != 2 || graph.Flow().Steps[1].Input.Source != "draft.output" {
		t.Fatal("lost exact flow/member selection")
	}
	flow := graph.Flow()
	flow.Steps[1].Member = "changed"
	*flow.Cases[0].Runs = 99
	flow.Cases[0].Assertions[0].Check.Value = "changed"
	report := graph.Report()
	report.AgentPlatforms[0].Platforms[0].OS = "changed"
	if graph.Flow().Steps[1].Member != "reviewer" || *graph.Flow().Cases[0].Runs != 3 || graph.Flow().Cases[0].Assertions[0].Check.Value != "8 hours" || graph.Report().AgentPlatforms[0].Platforms[0].OS != "linux" {
		t.Fatal("caller mutated verified graph inventory")
	}
	layout := writeTestOCILayout(t, root)
	before, err := os.ReadFile(filepath.Join(layout, "index.json"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := ValidatePath(layout); err == nil {
		t.Fatal("strict OCI reader accepted critical flow")
	}
	if _, err := ValidatePathFlowV1Alpha1(layout); err != nil {
		t.Fatal(err)
	}
	after, err := os.ReadFile(filepath.Join(layout, "index.json"))
	if err != nil {
		t.Fatal(err)
	}
	if string(before) != string(after) {
		t.Fatal("reader rewrote OCI identity")
	}
}

func TestFlowV1Alpha1GraphRefusals(t *testing.T) {
	want := map[string]string{
		"missing selector":           "experimental flow selector is missing",
		"noncritical selector":       "flow requires a critical selector",
		"missing digest":             "flow requires a critical selector",
		"unknown critical":           "unknown critical extension \"other.critical\"",
		"duplicate selector":         "invalid or duplicated",
		"wrong digest":               "flow document digest or canonical storage mismatch",
		"noncanonical":               "flow document digest or canonical storage mismatch",
		"extra file":                 "flow content closure contains an unsupported entry",
		"extra directory":            "flow content closure contains an unsupported entry",
		"flow symlink":               "flow content closure contains an unsupported entry",
		"unknown member":             "flow step references an unknown member",
		"undeclared edge":            "flow requirement references an undeclared invocation edge",
		"core descriptor":            "agent writer manifest digest mismatch",
		"agent scope":                "unknown critical extension \"kmx.flow.v1alpha1\"",
		"combined case bound":        "combined member and flow evaluation inventory exceeds limits",
		"combined run bound":         "combined member and flow evaluation inventory exceeds limits",
		"combined observation bound": "combined member and flow evaluation inventory exceeds limits",
	}
	for name, mutate := range map[string]func(*testing.T, string){
		"missing selector": func(t *testing.T, root string) {
			var s Suite
			readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &s)
			s.Extensions = nil
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, s)
		},
		"noncritical selector": func(t *testing.T, root string) {
			var s Suite
			readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &s)
			s.Extensions[len(s.Extensions)-1].Critical = false
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, s)
		},
		"missing digest": func(t *testing.T, root string) {
			var s Suite
			readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &s)
			s.Extensions[len(s.Extensions)-1].Digest = ""
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, s)
		},
		"unknown critical": func(t *testing.T, root string) {
			var s Suite
			readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &s)
			s.Extensions = append(s.Extensions, Extension{Name: "other.critical", Critical: true})
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, s)
		},
		"duplicate selector": func(t *testing.T, root string) {
			var s Suite
			readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &s)
			s.Extensions = append(s.Extensions, s.Extensions[len(s.Extensions)-1])
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, s)
		},
		"wrong digest": func(t *testing.T, root string) {
			var s Suite
			readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &s)
			s.Extensions[len(s.Extensions)-1].Digest = digestBytes([]byte("other"))
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, s)
		},
		"noncanonical": func(t *testing.T, root string) {
			p := filepath.Join(root, "coordination/flow.json")
			b, err := os.ReadFile(p)
			if err != nil {
				t.Fatal(err)
			}
			// Keep the raw binding valid so this reaches the canonical-storage check.
			b = append(b, '\n')
			mustWrite(t, root, "coordination/flow.json", b)
			var s Suite
			readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &s)
			s.Extensions[len(s.Extensions)-1].Digest = digestBytes(b)
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, s)
		},
		"extra file": func(t *testing.T, root string) { mustWrite(t, root, "coordination/extra.json", []byte("{}")) },
		"extra directory": func(t *testing.T, root string) {
			if err := os.Mkdir(filepath.Join(root, "coordination/extra"), 0700); err != nil {
				t.Fatal(err)
			}
		},
		"flow symlink": func(t *testing.T, root string) {
			p := filepath.Join(root, "coordination/flow.json")
			if err := os.Remove(p); err != nil {
				t.Fatal(err)
			}
			if err := os.Symlink("../instructions/writer.md", p); err != nil {
				t.Fatal(err)
			}
		},
		"unknown member": func(t *testing.T, root string) {
			rewriteFlow(t, root, func(f *FlowV1Alpha1) { f.Steps[1].Member = "missing" })
		},
		"undeclared edge": func(t *testing.T, root string) {
			rewriteFlow(t, root, func(f *FlowV1Alpha1) {
				f.EdgeRequirements = []FlowEdgeRequirementV1Alpha1{{From: "writer", To: "reviewer", Approval: "required"}}
			})
		},
		"core descriptor": func(t *testing.T, root string) {
			var s Suite
			readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &s)
			s.Agents[0].Descriptor.Size++
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, s)
		},
		"agent scope": func(t *testing.T, root string) {
			var s Suite
			readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &s)
			var a Agent
			readStrictJSON(t, filepath.Join(root, s.Agents[0].Path), &a)
			a.Extensions = append(a.Extensions, Extension{Name: "kmx.flow.v1alpha1", Critical: true})
			s.Agents[0].Descriptor = mustWriteJSON(t, root, s.Agents[0].Path, MediaTypeAgent, a)
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, s)
		},
		"combined case bound": func(t *testing.T, root string) {
			rewriteFlow(t, root, func(f *FlowV1Alpha1) {
				base := f.Cases[0]
				f.Cases = nil
				for i := 0; i < 127; i++ {
					c := base
					c.ID = "case" + strconv.Itoa(i)
					f.Cases = append(f.Cases, c)
				}
			})
		},
		"combined run bound": func(t *testing.T, root string) {
			rewriteFlow(t, root, func(f *FlowV1Alpha1) {
				base := f.Cases[0]
				f.Cases = nil
				for i, n := range []int{1000, 1000, 1000, 1000, 96} {
					c := base
					c.ID = "case" + strconv.Itoa(i)
					c.Runs = &n
					f.Cases = append(f.Cases, c)
				}
			})
		},
		"combined observation bound": func(t *testing.T, root string) {
			rewriteFlow(t, root, func(f *FlowV1Alpha1) {
				n := 1000
				f.Cases[0].Runs = &n
				f.Cases[0].Assertions = nil
				for i := 0; i < 32; i++ {
					f.Cases[0].Assertions = append(f.Cases[0].Assertions, FlowAssertionV1Alpha1{Step: "draft", Check: EvaluationAssertion{ID: "check" + strconv.Itoa(i), Type: "contains", Value: "answer"}})
				}
			})
		},
	} {
		t.Run(name, func(t *testing.T) {
			root := writeFlowSuite(t)
			mutate(t, root)
			message, ok := want[name]
			if !ok {
				t.Fatal("missing refusal expectation")
			}
			if _, err := ValidateDirectoryFlowV1Alpha1(root); err == nil || !strings.Contains(err.Error(), message) {
				t.Fatalf("got %v; want %s", err, message)
			}
		})
	}
}

func TestFlowV1Alpha1StrictJSONBeforeCanonicalStorage(t *testing.T) {
	root := writeFlowSuite(t)
	raw := []byte(`{"id":"first","id":"duplicate"}`)
	mustWrite(t, root, "coordination/flow.json", raw)
	var suite Suite
	readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
	suite.Extensions[len(suite.Extensions)-1].Digest = digestBytes(raw)
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
	if _, err := ValidateDirectoryFlowV1Alpha1(root); err == nil || err.Error() != "flow JSON is invalid" {
		t.Fatalf("strict JSON limits must precede canonicalization: %v", err)
	}
}

func TestFlowV1Alpha1DeclaredApproval(t *testing.T) {
	root := writeFlowSuite(t)
	var suite Suite
	readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
	var a Agent
	readStrictJSON(t, filepath.Join(root, suite.Agents[0].Path), &a)
	a.Invokes = []AgentInvoke{{Agent: "reviewer", MaxConcurrent: 1, MaxDepth: 1}}
	suite.Agents[0].Descriptor = mustWriteJSON(t, root, suite.Agents[0].Path, MediaTypeAgent, a)
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
	rewriteFlow(t, root, func(f *FlowV1Alpha1) {
		f.EdgeRequirements = []FlowEdgeRequirementV1Alpha1{{From: "writer", To: "reviewer", Approval: "required"}}
	})
	g, err := ValidateDirectoryFlowV1Alpha1(root)
	if err != nil {
		t.Fatal(err)
	}
	if g.Flow().EdgeRequirements[0].Approval != "required" {
		t.Fatal("lost author approval requirement")
	}
	// Storage validation does not dispatch or implement approval enforcement.
	if _, err := ValidateDirectory(root); err == nil {
		t.Fatal("experimental edge reinterpreted strict core")
	}
}
