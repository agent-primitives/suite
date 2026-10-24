package core

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/gowebpki/jcs"
)

type jsonConformanceCase struct {
	Name      string  `json:"name"`
	Target    string  `json:"target"`
	Input     *string `json:"input"`
	InputHex  *string `json:"inputHex"`
	Valid     bool    `json:"valid"`
	Canonical *string `json:"canonical"`
	Digest    *string `json:"digest"`
	Size      *int64  `json:"size"`
}

func (c jsonConformanceCase) inputBytes(t *testing.T) []byte {
	t.Helper()
	if c.Input != nil {
		return []byte(*c.Input)
	}
	data, err := hex.DecodeString(*c.InputHex)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func jsonConformanceCases(t *testing.T) []jsonConformanceCase {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "testdata", "conformance", "json-cases.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.HasSuffix(data, []byte("\n")) {
		t.Fatal("JSON corpus must end with a newline")
	}
	lines := bytes.Split(bytes.TrimSuffix(data, []byte("\n")), []byte("\n"))
	if len(lines) < 31 {
		t.Fatalf("JSON corpus has %d cases, want at least 31", len(lines))
	}
	var cases []jsonConformanceCase
	seen := map[string]bool{}
	for i, line := range lines {
		canonical, err := jcs.Transform(line)
		if err != nil || !bytes.Equal(canonical, line) {
			t.Fatalf("line %d is not canonical JSON: %v", i+1, err)
		}
		var c jsonConformanceCase
		decoder := json.NewDecoder(bytes.NewReader(line))
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&c); err != nil {
			t.Fatal(err)
		}
		if c.Name == "" || seen[c.Name] || (c.Input == nil) == (c.InputHex == nil) {
			t.Fatalf("line %d: missing/duplicate name or ambiguous input", i+1)
		}
		if c.Valid != (c.Canonical != nil) || c.Valid != (c.Digest != nil) || c.Valid != (c.Size != nil) {
			t.Fatalf("%s: canonical, digest and size required exactly for accepted cases", c.Name)
		}
		seen[c.Name] = true
		cases = append(cases, c)
	}
	return cases
}

func TestSharedJSONConformance(t *testing.T) {
	var accepted, refused int
	for _, c := range jsonConformanceCases(t) {
		t.Run(c.Name, func(t *testing.T) {
			var out any
			switch c.Target {
			case "json":
				out = new(any)
			case "descriptor":
				out = new(Descriptor)
			case "platform":
				out = new(Platform)
			default:
				t.Fatalf("unknown corpus target %q", c.Target)
			}
			input := c.inputBytes(t)
			err := Unmarshal(input, out)
			if !c.Valid {
				refused++
				if err == nil {
					t.Fatalf("accepted invalid input %q", input)
				}
				return
			}
			accepted++
			if err != nil {
				t.Fatal(err)
			}
			canonical, err := Marshal(out)
			if err != nil {
				t.Fatal(err)
			}
			digest, err := Digest(input)
			if err != nil {
				t.Fatal(err)
			}
			if string(canonical) != *c.Canonical || int64(len(canonical)) != *c.Size || digest != *c.Digest {
				t.Fatalf("canonical=%q size=%d digest=%s; want %q size=%d digest=%s", canonical, len(canonical), digest, *c.Canonical, *c.Size, *c.Digest)
			}
		})
	}
	if accepted == 0 || refused == 0 {
		t.Fatalf("corpus needs accepted and refused inputs: %d/%d", accepted, refused)
	}
}

func descriptorConformanceCases(t *testing.T, valid bool) []jsonConformanceCase {
	t.Helper()
	var cases []jsonConformanceCase
	for _, c := range jsonConformanceCases(t) {
		if c.Target == "descriptor" && c.Valid == valid {
			cases = append(cases, c)
		}
	}
	minimum := 9
	if valid {
		minimum = 3
	}
	if len(cases) < minimum {
		t.Fatalf("descriptor cases with valid=%t: %d, want at least %d", valid, len(cases), minimum)
	}
	return cases
}
