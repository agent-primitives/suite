package artifact

import (
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

// Extend the existing small evaluation fixture, sharing the member and cases.
func runtimeProfileSuite(t *testing.T) (string, Suite, []RuntimeProfile) {
	t.Helper()
	root, _ := writeEvaluationSuite(t, nil)
	var suite Suite
	readStrictJSON(t, filepath.Join(root, "agentsuite.json"), &suite)
	var build BuildProfile
	readStrictJSON(t, filepath.Join(root, suite.BuildProfiles[0].Path), &build)
	var base Composition
	readStrictJSON(t, filepath.Join(root, suite.Compositions[0].Path), &base)
	suite.Compositions = nil
	var profiles []RuntimeProfile
	for _, id := range []string{"orka", "sessions"} {
		impl := EvidenceImplementation{ID: id, Version: "1.0.0", Digest: digestBytes([]byte(id))}
		profile := RuntimeProfile{SchemaVersion: SpecVersion, MediaType: MediaTypeRuntimeProfile, ID: id,
			Runtime: impl, Harness: impl, Renderer: impl, ConfigurationABI: id + "-v1", ImageRequired: true}
		profile.Harness.Digest = build.Harness[0].Image.Digest
		path := "runtime-profiles/" + id + ".json"
		suite.RuntimeProfiles = append(suite.RuntimeProfiles, ManifestRef{ID: id, Path: path,
			Descriptor: mustWriteJSON(t, root, path, MediaTypeRuntimeProfile, profile)})
		composition := base
		composition.RuntimeProfile = id
		path = "compositions/writer-" + id + ".json"
		suite.Compositions = append(suite.Compositions, CompositionRef{Agent: base.Agent, Platform: base.Platform,
			RuntimeProfile: id, Path: path, Descriptor: mustWriteJSON(t, root, path, MediaTypeComposition, composition)})
		profiles = append(profiles, profile)
	}
	mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
	return root, suite, profiles
}

func TestRuntimeProfilesGraphAndReport(t *testing.T) {
	root, suite, _ := runtimeProfileSuite(t)
	validateSchemaJSON(t, compileReferenceSchema(t, "suite.schema.json"), string(mustJSON(t, suite)), true)
	for _, ref := range suite.Compositions {
		var c Composition
		readStrictJSON(t, filepath.Join(root, ref.Path), &c)
		validateSchemaJSON(t, compileReferenceSchema(t, "composition.schema.json"), string(mustJSON(t, c)), true)
	}
	report, err := ValidateDirectory(root)
	if err != nil {
		t.Fatal(err)
	}
	if report.Compositions != 2 || len(report.CompositionSelections) != 2 ||
		report.CompositionSelections[0].RuntimeProfile != "orka" || report.CompositionSelections[1].RuntimeProfile != "sessions" {
		t.Fatalf("profile selections lost: %+v", report)
	}
	if len(report.AgentPlatforms) != 1 || len(report.AgentPlatforms[0].Platforms) != 1 {
		t.Fatalf("platform inventory not deduplicated: %+v", report.AgentPlatforms)
	}
	for _, ref := range report.CompositionSelections {
		if ref.Digest == "" || ref.BuildProfile != "default" {
			t.Fatalf("incomplete selection: %+v", ref)
		}
	}
}

func TestRuntimeProfilesGraphRefusals(t *testing.T) {
	for name, want := range map[string]string{
		"duplicate-selection": "duplicate composition writer@linux/amd64@orka",
		"unknown":             "references unknown runtime profile missing",
		"selector-mismatch":   "composition writer@linux/amd64@orka identity does not match its reference",
		"mixed":               "mixes legacy and runtime profile selections",
		"profile-digest":      "runtime profile orka digest mismatch",
		"profile-size":        "runtime profile orka digest mismatch",
		"profile-media":       "runtime profile orka digest mismatch",
		"duplicate-profile":   `duplicate runtime profile "orka"`,
		"missing-profile":     "required file runtime-profiles/orka.json is missing",
		"profile-id":          "runtime profile reference orka points to other",
		"harness":             "runtime profile harness digest mismatch",
		"build":               `build profile "missing" does not support linux/amd64`,
		"platform":            `build profile "default" does not support linux/arm64`,
	} {
		t.Run(name, func(t *testing.T) {
			root, suite, profiles := runtimeProfileSuite(t)
			var c Composition
			readStrictJSON(t, filepath.Join(root, suite.Compositions[0].Path), &c)
			switch name {
			case "duplicate-selection":
				suite.Compositions = append(suite.Compositions, suite.Compositions[0])
			case "unknown":
				c.RuntimeProfile = "missing"
				suite.Compositions[0].RuntimeProfile = "missing"
			case "selector-mismatch":
				c.RuntimeProfile = "sessions"
			case "mixed":
				c.RuntimeProfile = ""
				suite.Compositions[0].RuntimeProfile = ""
			case "profile-digest":
				suite.RuntimeProfiles[0].Descriptor.Digest = digestBytes(nil)
			case "profile-size":
				suite.RuntimeProfiles[0].Descriptor.Size++
			case "profile-media":
				suite.RuntimeProfiles[0].Descriptor.MediaType = MediaTypeBuildProfile
			case "duplicate-profile":
				suite.RuntimeProfiles = append(suite.RuntimeProfiles, suite.RuntimeProfiles[0])
			case "missing-profile":
				if err := os.Remove(filepath.Join(root, suite.RuntimeProfiles[0].Path)); err != nil {
					t.Fatal(err)
				}
			case "profile-id":
				profiles[0].ID = "other"
				suite.RuntimeProfiles[0].Descriptor = mustWriteJSON(t, root, suite.RuntimeProfiles[0].Path, MediaTypeRuntimeProfile, profiles[0])
			case "harness":
				profiles[0].Harness.Digest = digestBytes(nil)
				suite.RuntimeProfiles[0].Descriptor = mustWriteJSON(t, root, suite.RuntimeProfiles[0].Path, MediaTypeRuntimeProfile, profiles[0])
			case "build":
				c.BuildProfile = "missing"
			case "platform":
				c.Platform.Architecture = "arm64"
				suite.Compositions[0].Platform = c.Platform
			}
			suite.Compositions[0].Descriptor = mustWriteJSON(t, root, suite.Compositions[0].Path, MediaTypeComposition, c)
			mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
			if _, err := ValidateDirectory(root); err == nil || !strings.Contains(err.Error(), want) {
				t.Fatalf("want refusal containing %q, got %v", want, err)
			}
		})
	}
}

func TestRuntimeProfileSchemaDecoderParity(t *testing.T) {
	_, _, profiles := runtimeProfileSuite(t)
	data, err := json.Marshal(profiles[0])
	if err != nil {
		t.Fatal(err)
	}
	var valid map[string]any
	if err := json.Unmarshal(data, &valid); err != nil {
		t.Fatal(err)
	}
	schema := compileReferenceSchema(t, "runtime-profile.schema.json")
	check := func(t *testing.T, doc map[string]any, want bool) {
		t.Helper()
		b, err := json.Marshal(doc)
		if err != nil {
			t.Fatal(err)
		}
		validateSchemaJSON(t, schema, string(b), want)
		var p RuntimeProfile
		if err := Unmarshal(b, &p); (err == nil) != want {
			t.Fatalf("decoder parity want %v: %v", want, err)
		}
	}
	check(t, valid, true)
	for key := range valid {
		for _, mode := range []string{"missing", "null"} {
			t.Run(key+"/"+mode, func(t *testing.T) {
				var doc map[string]any
				_ = json.Unmarshal(data, &doc)
				if mode == "missing" {
					delete(doc, key)
				} else {
					doc[key] = nil
				}
				check(t, doc, false)
			})
		}
	}
	for _, field := range []string{"runtime", "harness", "renderer"} {
		for _, key := range []string{"id", "version", "digest", "unknown"} {
			for _, mode := range []string{"missing", "null", "empty"} {
				t.Run(field+"/"+key+"/"+mode, func(t *testing.T) {
					var doc map[string]any
					_ = json.Unmarshal(data, &doc)
					child := doc[field].(map[string]any)
					if key == "unknown" {
						child[key] = true
					} else if mode == "missing" {
						delete(child, key)
					} else if mode == "null" {
						child[key] = nil
					} else {
						child[key] = ""
					}
					check(t, doc, false)
				})
			}
		}
	}
	for _, value := range []string{"", strings.Repeat("a", 129), "https://example.test/abi"} {
		valid["configurationABI"] = value
		check(t, valid, false)
	}
	valid["configurationABI"] = "consumer-owned-v2"
	valid["imageRequired"] = false
	check(t, valid, true)
	for _, key := range []string{"agent", "model", "policy", "cases", "environment", "credentials"} {
		valid[key] = "forbidden"
		check(t, valid, false)
		delete(valid, key)
	}
}

func TestRuntimeProfileOptionalWireParity(t *testing.T) {
	root, suite, _ := runtimeProfileSuite(t)
	for _, field := range []string{"runtimeProfiles", "runtimeProfile"} {
		for _, value := range []any{nil, "", []any{}} {
			t.Run(field+"/"+string(mustJSON(t, value)), func(t *testing.T) {
				var doc map[string]any
				var out any
				schemaName := "suite.schema.json"
				if field == "runtimeProfiles" {
					_ = json.Unmarshal(mustJSON(t, suite), &doc)
					out = &Suite{}
				} else {
					var c Composition
					readStrictJSON(t, filepath.Join(root, suite.Compositions[0].Path), &c)
					_ = json.Unmarshal(mustJSON(t, c), &doc)
					out = &Composition{}
					schemaName = "composition.schema.json"
				}
				doc[field] = value
				b := mustJSON(t, doc)
				validateSchemaJSON(t, compileReferenceSchema(t, schemaName), string(b), false)
				if err := Unmarshal(b, out); err == nil {
					t.Fatal("invalid optional value accepted")
				}
				if field == "runtimeProfile" {
					ref := map[string]any{}
					_ = json.Unmarshal(mustJSON(t, suite.Compositions[0]), &ref)
					ref[field] = value
					if err := Unmarshal(mustJSON(t, ref), &CompositionRef{}); err == nil {
						t.Fatal("invalid reference selector accepted")
					}
					doc = map[string]any{}
					_ = json.Unmarshal(mustJSON(t, suite), &doc)
					doc["compositions"] = []any{ref}
					validateSchemaJSON(t, compileReferenceSchema(t, "suite.schema.json"), string(mustJSON(t, doc)), false)
				}
			})
		}
	}
}

func mustJSON(t *testing.T, value any) []byte {
	t.Helper()
	b, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func TestRuntimeProfileReferencesShape(t *testing.T) {
	_, suite, _ := runtimeProfileSuite(t)
	for _, name := range []string{"null-entry", "missing-id", "null-id", "empty-id", "missing-path", "null-path", "empty-path", "missing-descriptor", "null-descriptor", "unknown", "null-version"} {
		t.Run(name, func(t *testing.T) {
			var ref map[string]any
			_ = json.Unmarshal(mustJSON(t, suite.RuntimeProfiles[0]), &ref)
			parts := strings.SplitN(name, "-", 2)
			if len(parts) == 2 {
				switch parts[0] {
				case "missing":
					delete(ref, parts[1])
				case "null":
					ref[parts[1]] = nil
				case "empty":
					ref[parts[1]] = ""
				}
			} else {
				ref["unknown"] = true
			}
			var entry any = ref
			if name == "null-entry" {
				entry = nil
			}
			var doc map[string]any
			_ = json.Unmarshal(mustJSON(t, suite), &doc)
			doc["runtimeProfiles"] = []any{entry}
			data := mustJSON(t, doc)
			validateSchemaJSON(t, compileReferenceSchema(t, "suite.schema.json"), string(data), false)
			if err := Unmarshal(data, &Suite{}); err == nil {
				t.Fatal("malformed profile reference decoded")
			}
		})
	}
}

func TestRuntimeProfileReferencePaths(t *testing.T) {
	_, suite, _ := runtimeProfileSuite(t)
	schema := compileReferenceSchema(t, "suite.schema.json")
	for _, tc := range []struct {
		name, path  string
		schemaValid bool
	}{
		{"absolute", "/runtime-profiles/orka.json", false},
		{"backslash", `runtime-profiles\orka.json`, false},
		{"overlong", strings.Repeat("a", 1025), false},
		// Schema shape alone permits traversal; semantic decoding is stricter.
		{"traversal", "../orka.json", true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			suite.RuntimeProfiles[0].Path = tc.path
			data := mustJSON(t, suite)
			validateSchemaJSON(t, schema, string(data), tc.schemaValid)
			if err := Unmarshal(data, &Suite{}); err == nil {
				t.Fatal("unsafe runtime profile reference path decoded")
			}
		})
	}
}

func TestRuntimeProfilesLegacyRoundTrip(t *testing.T) {
	for _, name := range []string{"agentsuite.json", "compositions/writer-linux-amd64.json"} {
		data, err := os.ReadFile(filepath.Join("../../testdata/minimal", name))
		if err != nil {
			t.Fatal(err)
		}
		var value any = &Suite{}
		if strings.HasPrefix(name, "compositions/") {
			value = &Composition{}
		}
		if err := Unmarshal(data, value); err != nil {
			t.Fatal(err)
		}
		roundtrip, err := Marshal(value)
		if err != nil {
			t.Fatal(err)
		}
		before, _ := Digest(data)
		after, _ := Digest(roundtrip)
		want := "sha256:59b19197bc5a053ec68968dfd9f990d50c24829c5761f251559f26cff6ba0711"
		if strings.HasPrefix(name, "compositions/") {
			want = "sha256:c19a6173a3bad6723b5f4c36f49c8ee21afbd65317d9c9c4275ebd130b2223d5"
		}
		if before != want || after != want {
			t.Fatalf("legacy identity changed: %s / %s; want %s", before, after, want)
		}
	}
}

func TestRuntimeProfileDiffSelectiveInvocationImpact(t *testing.T) {
	before, suite, profiles := runtimeProfileSuite(t)
	var base Agent
	readStrictJSON(t, filepath.Join(before, suite.Agents[0].Path), &base)
	var c Composition
	readStrictJSON(t, filepath.Join(before, suite.Compositions[0].Path), &c)
	for _, id := range []string{"observer", "caller"} {
		a := base
		a.ID, a.Evals = id, nil
		if id == "caller" {
			a.Invokes = []AgentInvoke{{Agent: "writer", MaxConcurrent: 1, MaxDepth: 1}}
		}
		path := "agents/" + id + ".json"
		suite.Agents = append(suite.Agents, ManifestRef{ID: id, Path: path, Descriptor: mustWriteJSON(t, before, path, MediaTypeAgent, a)})
		composition := c
		composition.Agent = id
		path = "compositions/" + id + ".json"
		suite.Compositions = append(suite.Compositions, CompositionRef{Agent: id, Platform: c.Platform, RuntimeProfile: "orka", Path: path,
			Descriptor: mustWriteJSON(t, before, path, MediaTypeComposition, composition)})
	}
	mustWriteJSON(t, before, "agentsuite.json", MediaTypeSuite, suite)
	after := copyAgentSuiteDirectory(t, before)
	profiles[1].ConfigurationABI = "consumer-owned-v2"
	suite.RuntimeProfiles[1].Descriptor = mustWriteJSON(t, after, suite.RuntimeProfiles[1].Path, MediaTypeRuntimeProfile, profiles[1])
	mustWriteJSON(t, after, "agentsuite.json", MediaTypeSuite, suite)
	report, err := DiffPaths(before, after)
	if err != nil {
		t.Fatal(err)
	}
	want := []AffectedAgent{{ID: "caller", Reasons: []string{"invoked agent writer affected"}}, {ID: "writer", Reasons: []string{"runtime profile sessions modified"}}}
	if !reflect.DeepEqual(report.AffectedAgents, want) {
		t.Fatalf("wrong selective impact: %+v", report.AffectedAgents)
	}
}

func TestRuntimeProfilesDiff(t *testing.T) {
	before, suite, profiles := runtimeProfileSuite(t)
	after := copyAgentSuiteDirectory(t, before)
	profiles[1].ConfigurationABI = "sessions-v2"
	suite.RuntimeProfiles[1].Descriptor = mustWriteJSON(t, after, suite.RuntimeProfiles[1].Path, MediaTypeRuntimeProfile, profiles[1])
	mustWriteJSON(t, after, "agentsuite.json", MediaTypeSuite, suite)
	report, err := DiffPaths(before, after)
	if err != nil {
		t.Fatal(err)
	}
	if len(report.Changes) != 1 || report.Changes[0].Kind != "runtimeProfile" || report.Changes[0].ID != "sessions" ||
		len(report.AffectedAgents) != 1 || !reflect.DeepEqual(report.AffectedAgents[0].Reasons, []string{"runtime profile sessions modified"}) {
		t.Fatalf("profile diff lost or over-expanded: %+v", report)
	}
	// Both same-platform compositions must remain separate records.
	var c Composition
	readStrictJSON(t, filepath.Join(after, suite.Compositions[0].Path), &c)
	c.BuildProfile = "alternate"
	var build BuildProfile
	readStrictJSON(t, filepath.Join(after, suite.BuildProfiles[0].Path), &build)
	build.ID = "alternate"
	path := "build-profiles/alternate.json"
	suite.BuildProfiles = append(suite.BuildProfiles, ManifestRef{ID: build.ID, Path: path, Descriptor: mustWriteJSON(t, after, path, MediaTypeBuildProfile, build)})
	suite.Compositions[0].Descriptor = mustWriteJSON(t, after, suite.Compositions[0].Path, MediaTypeComposition, c)
	mustWriteJSON(t, after, "agentsuite.json", MediaTypeSuite, suite)
	report, err = DiffPaths(before, after)
	if err != nil {
		t.Fatal(err)
	}
	found := false
	for _, change := range report.Changes {
		if change.Kind == "composition" {
			if change.ID != "writer@linux/amd64@orka" {
				t.Fatalf("wrong composition key: %+v", change)
			}
			found = true
		}
	}
	if !found {
		t.Fatal("same-platform composition overwritten")
	}
}
