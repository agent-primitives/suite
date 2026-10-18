package policy

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/gowebpki/jcs"
)

// decodeCase is one line of testdata/decode-cases.jsonl. The corpus is plain
// canonical JSON so that any implementation of the policy wire format can run
// the same refusal and canonical-bytes expectations.
type decodeCase struct {
	Name      string  `json:"name"`
	Input     *string `json:"input"`
	InputHex  *string `json:"inputHex"`
	Valid     bool    `json:"valid"`
	Canonical *string `json:"canonical"`
	Digest    *string `json:"digest"`
}

func TestSharedDecodeCases(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("testdata", "decode-cases.jsonl"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.HasSuffix(data, []byte("\n")) {
		t.Fatal("decode-cases.jsonl must end with a newline")
	}
	lines := bytes.Split(bytes.TrimSuffix(data, []byte("\n")), []byte("\n"))
	// Guard against an accidentally truncated corpus becoming a green run.
	if len(lines) < 150 {
		t.Fatalf("decode-cases.jsonl has %d cases, want at least 150", len(lines))
	}
	names := make(map[string]bool, len(lines))
	var accepted, refused int
	for i, line := range lines {
		canonicalLine, err := jcs.Transform(line)
		if err != nil || !bytes.Equal(canonicalLine, line) {
			t.Fatalf("line %d is not canonical JCS: %v", i+1, err)
		}
		var tc decodeCase
		decoder := json.NewDecoder(bytes.NewReader(line))
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&tc); err != nil {
			t.Fatalf("line %d: %v", i+1, err)
		}
		if tc.Name == "" || names[tc.Name] {
			t.Fatalf("line %d: empty or duplicate case name %q", i+1, tc.Name)
		}
		names[tc.Name] = true
		if (tc.Input == nil) == (tc.InputHex == nil) {
			t.Fatalf("%s: exactly one of input and inputHex is required", tc.Name)
		}
		if tc.Valid != (tc.Canonical != nil) || tc.Valid != (tc.Digest != nil) {
			t.Fatalf("%s: canonical and digest are required exactly for valid cases", tc.Name)
		}
		var input []byte
		if tc.Input != nil {
			input = []byte(*tc.Input)
		} else if input, err = hex.DecodeString(*tc.InputHex); err != nil {
			t.Fatalf("%s: %v", tc.Name, err)
		}
		if tc.Valid {
			accepted++
		} else {
			refused++
		}
		t.Run(tc.Name, func(t *testing.T) {
			suite, err := DecodeSuitePolicy(input)
			if !tc.Valid {
				if err == nil {
					t.Fatalf("accepted %q", input)
				}
				return
			}
			if err != nil {
				t.Fatalf("refused %q: %v", input, err)
			}
			canonical, err := CanonicalBytes(EffectivePolicy(suite))
			if err != nil {
				t.Fatal(err)
			}
			digest := Digest(canonical)
			if string(canonical) != *tc.Canonical || digest != *tc.Digest {
				t.Fatalf("canonical = %s, digest = %s; want %s, %s", canonical, digest, *tc.Canonical, *tc.Digest)
			}
			payload := ProviderPayload{Version: suite.Version, PolicyBytes: canonical, PolicyDigest: digest, RequiredCapabilities: suite.RequiredCapabilities}
			if err := VerifyPayload(payload); err != nil {
				t.Fatalf("canonical payload: %v", err)
			}
		})
	}
	if accepted == 0 || refused == 0 {
		t.Fatalf("corpus must contain both accepted and refused cases: accepted=%d refused=%d", accepted, refused)
	}
}
