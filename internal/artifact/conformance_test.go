package artifact

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/gowebpki/jcs"
)

// Like the policy corpus, each line is canonical JSON with committed expectations.
func sharedJSONLines[T any](t *testing.T, name string, minimum int) []T {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "..", "testdata", "conformance", name))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.HasSuffix(data, []byte("\n")) {
		t.Fatalf("%s must end with a newline", name)
	}
	lines := bytes.Split(bytes.TrimSuffix(data, []byte("\n")), []byte("\n"))
	if len(lines) < minimum {
		t.Fatalf("%s has %d cases, want at least %d", name, len(lines), minimum)
	}
	var cases []T
	for i, line := range lines {
		canonical, err := jcs.Transform(line)
		if err != nil || !bytes.Equal(canonical, line) {
			t.Fatalf("%s line %d is not canonical JSON: %v", name, i+1, err)
		}
		var c T
		decoder := json.NewDecoder(bytes.NewReader(line))
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&c); err != nil {
			t.Fatal(err)
		}
		cases = append(cases, c)
	}
	return cases
}

type packageConformanceCase struct {
	Name           string `json:"name"`
	Path           string `json:"path"`
	Form           string `json:"form"`
	Valid          bool   `json:"valid"`
	ContentDigest  string `json:"contentDigest"`
	ManifestDigest string `json:"manifestDigest"`
	RootDigest     string `json:"rootDigest"`
}

func decodePackageConformance(data []byte) ([]packageConformanceCase, error) {
	var cases []packageConformanceCase
	err := decodeStrict(data, &cases)
	return cases, err
}

func TestPackageCorpusRejectsTrailingData(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "..", "testdata", "conformance", "packages.json"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := decodePackageConformance(data); err != nil {
		t.Fatalf("valid corpus refused: %v", err)
	}
	for _, suffix := range []string{" []", " trailing-garbage"} {
		t.Run(suffix, func(t *testing.T) {
			if _, err := decodePackageConformance(append(bytes.Clone(data), suffix...)); err == nil {
				t.Fatal("accepted trailing corpus data")
			}
		})
	}
}

func packageConformanceCases(t *testing.T) []packageConformanceCase {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "..", "testdata", "conformance", "packages.json"))
	if err != nil {
		t.Fatal(err)
	}
	cases, err := decodePackageConformance(data)
	if err != nil {
		t.Fatal(err)
	}
	if len(cases) < 7 {
		t.Fatalf("package corpus has %d cases, want at least 7", len(cases))
	}
	seen := map[string]bool{}
	for _, c := range cases {
		if c.Name == "" || seen[c.Name] || c.Path == "" || (c.Form != "directory" && c.Form != "oci") {
			t.Fatalf("invalid or duplicate package case: %+v", c)
		}
		if c.Valid && (!IsValidDigest(c.ContentDigest) ||
			(c.Form == "oci" && !IsValidDigest(c.ManifestDigest)) ||
			(c.Form == "directory" && !IsValidDigest(c.RootDigest))) {
			t.Fatalf("missing expected identities: %+v", c)
		}
		seen[c.Name] = true
	}
	return cases
}

func packageConformanceInput(t *testing.T, c packageConformanceCase) string {
	t.Helper()
	root := copyAgentSuiteDirectory(t, filepath.Join("..", "..", "testdata", "conformance", filepath.FromSlash(c.Path)))
	secureDirectoryFixture(t, root)
	return root
}

func packageConformanceNamed(t *testing.T, name string) packageConformanceCase {
	t.Helper()
	for _, c := range packageConformanceCases(t) {
		if c.Name == name {
			return c
		}
	}
	t.Fatalf("missing package case %q", name)
	return packageConformanceCase{}
}

func TestLooseDirectorySharedCorpus(t *testing.T) {
	count := 0
	for _, c := range packageConformanceCases(t) {
		if c.Form != "directory" {
			continue
		}
		count++
		t.Run(c.Name, func(t *testing.T) {
			if !c.Valid {
				t.Fatal("unexpected refused directory case: add its Go-side refusal assertion")
			}
			root := packageConformanceInput(t, c)
			if _, err := ValidatePath(root); err != nil {
				t.Fatal(err)
			}
			data, err := os.ReadFile(filepath.Join(root, "agentsuite.json"))
			if err != nil {
				t.Fatal(err)
			}
			digest, err := canonicalDigest(data)
			if err != nil || digest != c.RootDigest {
				t.Fatalf("root digest=%s, err=%v; want %s", digest, err, c.RootDigest)
			}
			report, err := DiffPaths(root, root)
			if err != nil {
				t.Fatal(err)
			}
			if report.Before.ContentDigest != c.ContentDigest {
				t.Fatalf("content digest=%s; want %s", report.Before.ContentDigest, c.ContentDigest)
			}
		})
	}
	if count < 3 {
		t.Fatalf("directory corpus has %d cases, want at least 3", count)
	}
}

func TestSharedImageReferenceConformance(t *testing.T) {
	data, err := os.ReadFile("../../testdata/conformance/image-reference-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		Name     string `json:"name"`
		ImageRef string `json:"imageRef"`
		Valid    bool   `json:"valid"`
	}
	if err := decodeStrict(data, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) == 0 {
		t.Fatal("empty image-reference corpus")
	}
	schema := compileReferenceSchema(t, "build-profile.schema.json")
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			if err := ValidateImageReference(c.ImageRef); (err == nil) != c.Valid {
				t.Fatalf("image-reference error = %v, want valid=%t", err, c.Valid)
			}
			var profile BuildProfile
			readStrictJSON(t, "../../testdata/minimal/build-profiles/default.json", &profile)
			for _, images := range [][]PlatformImage{profile.RuntimeBase, profile.Harness} {
				for i := range images {
					images[i].ImageRef = c.ImageRef
				}
			}
			document, err := json.Marshal(profile)
			if err != nil {
				t.Fatal(err)
			}
			validateSchemaJSON(t, schema, string(document), c.Valid)
		})
	}
}
