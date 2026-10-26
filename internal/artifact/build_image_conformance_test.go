package artifact

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

// The general image-reference helper is deliberately broader than the authored
// build-profile schema. Preserve both contracts, not a legacy schema exception.
func TestSharedBuildImageBoundary(t *testing.T) {
	data, err := os.ReadFile("../../testdata/conformance/image-reference-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		Name        string `json:"name"`
		ImageRef    string `json:"imageRef"`
		Valid       bool   `json:"valid"`
		SchemaValid *bool  `json:"schemaValid,omitempty"`
	}
	if err := decodeStrict(data, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) != 48 {
		t.Fatalf("image corpus count = %d, want 48", len(cases))
	}
	schema := compileReferenceSchema(t, "build-profile.schema.json")
	full := map[string]bool{
		"legacy-uppercase-registry": false, "legacy-double-underscore": false, "legacy-double-hyphen": false,
		"ipv6-uppercase": true, "dns-double-hyphen-control": true, "mixed-repository-separators-control": true,
	}
	seen := map[string]bool{}
	for _, row := range cases {
		if row.Name == "" || seen[row.Name] {
			t.Fatal("empty or duplicate image case name")
		}
		seen[row.Name] = true
		for _, group := range []string{"runtimeBase", "harness"} {
			t.Run(row.Name+"/"+group, func(t *testing.T) {
				var profile BuildProfile
				readStrictJSON(t, "../../testdata/minimal/build-profiles/default.json", &profile)
				images := profile.RuntimeBase
				if group == "harness" {
					images = profile.Harness
				}
				images[0].ImageRef = row.ImageRef
				if _, digest, ok := strings.Cut(row.ImageRef, "@"); ok {
					images[0].Image.Digest = digest
				}
				raw, err := json.Marshal(profile)
				if err != nil {
					t.Fatal(err)
				}
				schemaValid := row.Valid
				if row.SchemaValid != nil {
					schemaValid = *row.SchemaValid
				}
				validateSchemaJSON(t, schema, string(raw), schemaValid)
				valid := row.Valid && schemaValid
				if err := validateBuildProfile(profile); (err == nil) != valid {
					t.Fatalf("owning build validation = %v, want valid=%t", err, valid)
				}
				if want, exercise := full[row.Name]; exercise {
					if valid != want || schemaValid != want {
						t.Fatal("boundary/control schema expectation changed")
					}
					root := writeMinimalSuite(t)
					var suite Suite
					readStrictJSON(t, root+"/agentsuite.json", &suite)
					suite.BuildProfiles[0].Descriptor = mustWriteJSON(t, root,
						"build-profiles/default.json", MediaTypeBuildProfile, profile)
					mustWriteJSON(t, root, "agentsuite.json", MediaTypeSuite, suite)
					secureDirectoryFixture(t, root)
					_, err := ValidatePath(root)
					if (err == nil) != valid {
						t.Fatalf("full package validation = %v, want valid=%t", err, valid)
					}
					if !valid && !strings.Contains(err.Error(), "authored build-profile syntax") {
						t.Fatalf("refusal did not reach authored boundary: %v", err)
					}
				}
			})
		}
	}
	for name := range full {
		if !seen[name] {
			t.Fatalf("required boundary/control missing: %s", name)
		}
	}
}
