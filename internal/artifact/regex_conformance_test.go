package artifact

import (
	"bytes"
	"encoding/json"
	"os"
	"regexp"
	"testing"
)

// Syntax oracle only: no authored expression is executed.
func TestSharedRegexCases(t *testing.T) {
	raw, err := os.ReadFile("../../testdata/conformance/regex-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var corpus struct {
		Cases []struct {
			Name    string  `json:"name"`
			Pattern *string `json:"pattern"`
			Valid   *bool   `json:"valid"`
		} `json:"cases"`
	}
	if err := decodeStrict(raw, &corpus); err != nil {
		t.Fatal(err)
	}
	top := sharedGraphFields(t, raw, "cases")
	var rows []json.RawMessage
	if err := json.Unmarshal(top["cases"], &rows); err != nil {
		t.Fatal(err)
	}
	names := map[string]bool{}
	for i, row := range corpus.Cases {
		fields := sharedGraphFields(t, rows[i], "name", "pattern", "valid")
		for key, value := range fields {
			if bytes.Equal(value, []byte("null")) {
				t.Fatalf("%s: null %s", row.Name, key)
			}
		}
		if row.Name == "" || names[row.Name] || row.Pattern == nil || row.Valid == nil {
			t.Fatalf("incomplete/duplicate regex row %q", row.Name)
		}
		names[row.Name] = true
		t.Run(row.Name, func(t *testing.T) {
			_, err := regexp.Compile(*row.Pattern)
			if (err == nil) != *row.Valid {
				t.Fatalf("Compile(%q) = %v; want valid=%t", *row.Pattern, err, *row.Valid)
			}
		})
	}
	for _, name := range []string{"empty", "named-unicode", "named-digit", "byte-escape", "byte-quoted", "byte-after-posix",
		"property-spaces", "property-Old_Italic-exact", "property-SignWriting-exact", "property-Assigned-exact",
		"repeat-nested-over", "budget-literal", "budget-letter", "budget-folded-nonword", "budget-dotall",
		"budget-complement", "budget-quoted-utf8", "budget-nullable-range", "budget-anchor-star",
		"repeat-range-nested-over", "repeat-range-nested-zero-barrier", "repeat-range-min-leading-zero",
		"repeat-range-bare-flags", "class-hex-range-reversed", "nul", "newline", "vt", "nel", "nbsp", "bom"} {
		if !names[name] {
			t.Fatalf("required regex case %q missing", name)
		}
	}
	if len(corpus.Cases) != 696 {
		t.Fatalf("truncated regex corpus: %d", len(corpus.Cases))
	}
}

// The Python differential supplies bounded generated expressions through a file;
// this test-only oracle is not part of the reader or its deployment.
func TestRegexDifferentialOracle(t *testing.T) {
	path := os.Getenv("AGENTSUITE_REGEX_ORACLE")
	if path == "" {
		return
	}
	var patterns []string
	readStrictJSON(t, path, &patterns)
	valid := make([]bool, len(patterns))
	for i, pattern := range patterns {
		_, err := regexp.Compile(pattern)
		valid[i] = err == nil
	}
	raw, err := json.Marshal(valid)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path+".result", raw, 0600); err != nil {
		t.Fatal(err)
	}
}
