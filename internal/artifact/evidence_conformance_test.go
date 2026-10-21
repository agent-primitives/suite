package artifact

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestEvidenceIndependentExpectationsComplete(t *testing.T) {
	layout, expected, e := evidenceFixture(t, nil)
	original, _ := json.Marshal(expected)
	var value any
	if err := json.Unmarshal(original, &value); err != nil {
		t.Fatal(err)
	}
	var walk func(any)
	walk = func(v any) {
		object, ok := v.(map[string]any)
		if !ok {
			return
		}
		for key, child := range object {
			switch child.(type) {
			case string:
				if child == "" {
					continue
				}
				object[key] = ""
			case float64:
				object[key] = float64(0)
			default:
				walk(child)
				continue
			}
			b, _ := json.Marshal(value)
			var incomplete ExpectedEvaluation
			if err := json.Unmarshal(b, &incomplete); err != nil {
				t.Fatal(err)
			}
			evidenceCode(t, layout, incomplete, evidenceBytes(t, e), "missing")
			object[key] = child
		}
	}
	walk(value)
}

func TestEvidenceRawManifestAndArtifactBinding(t *testing.T) {
	t.Run("raw-not-jcs", func(t *testing.T) {
		layout, expected, e := evidenceFixture(t, nil)
		raw, err := os.ReadFile(filepath.Join(layout, "blobs/sha256", strings.TrimPrefix(e.Subject.Manifest.Digest, "sha256:")))
		if err != nil {
			t.Fatal(err)
		}
		canonical, err := Digest(raw)
		if err != nil {
			t.Fatal(err)
		}
		if canonical == e.Subject.Manifest.Digest {
			t.Fatal("fixture must distinguish raw from JCS manifest identity")
		}
		e.Subject.Manifest.Digest = canonical
		expected.Subject = e.Subject
		evidenceCode(t, layout, expected, evidenceBytes(t, e), "subject")
	})
	t.Run("corrupt-manifest", func(t *testing.T) {
		layout, expected, e := evidenceFixture(t, nil)
		mustWrite(t, layout, "blobs/sha256/"+strings.TrimPrefix(e.Subject.Manifest.Digest, "sha256:"), []byte("PRIVATE_ARTIFACT_CANARY"))
		got, err := VerifyEvaluation(layout, expected, bytes.NewReader(evidenceBytes(t, e)))
		if got != nil || err == nil || strings.Contains(err.Error(), "PRIVATE_") {
			t.Fatalf("unsafe artifact refusal: %v", err)
		}
	})
}

func TestEvidenceResourceBounds(t *testing.T) {
	for _, tt := range []struct {
		name             string
		runs, assertions int
	}{
		{"total-runs", 1000, 1}, // expanded below to five claimed cases
		{"total-rows", 1000, 17},
	} {
		t.Run(tt.name, func(t *testing.T) {
			layout, expected, e := evidenceFixture(t, func(c *EvaluationCase) {
				c.Runs = &tt.runs
				c.Assertions = nil
				for i := 0; i < tt.assertions; i++ {
					c.Assertions = append(c.Assertions, EvaluationAssertion{ID: string(rune('a' + i)), Type: "contains", Value: "public"})
				}
			})
			if tt.name == "total-runs" {
				e.Results = append(e.Results, e.Results[0], e.Results[0], e.Results[0])
			}
			evidenceCode(t, layout, expected, evidenceBytes(t, e), "limit")
		})
	}
	layout, expected, e := evidenceFixture(t, nil)
	for _, raw := range []string{strings.Repeat("[", 101) + "0" + strings.Repeat("]", 101), `{"private":` + strings.Repeat("[", 101) + "0" + strings.Repeat("]", 101) + `}`} {
		got, err := VerifyEvaluation(layout, expected, strings.NewReader(raw))
		if got != nil || err == nil {
			t.Fatal("deep document accepted")
		}
	}
	// Both omission and future status spellings are rejected at the wire boundary.
	for _, replacement := range []string{`"status":"errored"`, `"status":null`} {
		data := strings.Replace(string(evidenceBytes(t, e)), `"status":"completed"`, replacement, 1)
		evidenceCode(t, layout, expected, []byte(data), "malformed")
	}
}

func TestEvidenceDetachedFixtures(t *testing.T) {
	layout, expected, _ := evidenceFixture(t, nil)
	schema := compileReferenceSchema(t, "eval-evidence.schema.json")
	for _, tt := range []struct {
		name  string
		valid bool
	}{{"valid.json", true}, {"private-fields.json", false}} {
		t.Run(tt.name, func(t *testing.T) {
			data, err := os.ReadFile(filepath.Join("../../testdata/evidence", tt.name))
			if err != nil {
				t.Fatal(err)
			}
			validateSchemaJSON(t, schema, string(data), tt.valid)
			if tt.valid {
				evidenceCode(t, layout, expected, data, "")
				if strings.Contains(string(data), "PRIVATE_") {
					t.Fatal("positive fixture contains private payload")
				}
			} else {
				got, err := VerifyEvaluation(layout, expected, bytes.NewReader(data))
				if got != nil || err == nil || strings.Contains(err.Error(), "PRIVATE_") {
					t.Fatalf("unsafe private fixture refusal: %v", err)
				}
			}
		})
	}
}
