package policy

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func sample() SuitePolicy {
	return SuitePolicy{
		Version:              SchemaVersion,
		DenyWritePaths:       []string{"/workspace/cache", "/workspace/source", "/workspace/cache"},
		RequiredCapabilities: []string{FilesystemDenyWrite},
	}
}

func TestCanonicalVectorFilesAgree(t *testing.T) {
	policyPath := filepath.Join("testdata", "effective-policy-v1.json")
	digestPath := filepath.Join("testdata", "effective-policy-v1.sha256")
	data, err := os.ReadFile(policyPath)
	if err != nil {
		t.Fatal(err)
	}
	wantDigest, err := os.ReadFile(digestPath)
	if err != nil {
		t.Fatal(err)
	}
	if got, want := Digest(data), strings.TrimSpace(string(wantDigest)); got != want {
		t.Fatalf("fixture digest mismatch: got %s, want %s", got, want)
	}
	var effective EffectivePolicy
	if err := decodeStrict(data, &effective); err != nil {
		t.Fatal(err)
	}
	canonical, err := CanonicalBytes(effective)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(canonical, data) {
		t.Fatalf("fixture is not canonical: %s", data)
	}

	resolved, err := Resolve(sample(), AdministrativePolicy{DenyWritePaths: []string{"/etc/secrets"}})
	if err != nil {
		t.Fatal(err)
	}
	generated, err := CanonicalBytes(resolved)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(generated, data) {
		t.Fatalf("fixture differs from resolved policy: %s", generated)
	}
}

func TestSuitePolicyDecodeIsClosed(t *testing.T) {
	valid := `{"version":"agentsuite.policy/v1","denyWritePaths":["/a"],"requiredCapabilities":["filesystem/deny-write/v1"]}`
	bad := []string{
		`{"version":"agentsuite.policy/v1","denyWritePaths":["relative"],"requiredCapabilities":["filesystem/deny-write/v1"]}`,
		`{"version":"agentsuite.policy/v1","denyWritePaths":["/a"],"requiredCapabilities":["filesystem/deny-write/v1"],"extra":1}`,
		`{"version":"agentsuite.policy/v1","version":"agentsuite.policy/v1","denyWritePaths":["/a"],"requiredCapabilities":["filesystem/deny-write/v1"]}`,
		`{"version":"future","denyWritePaths":["/a"],"requiredCapabilities":["filesystem/deny-write/v1"]}`,
		`{"version":"agentsuite.policy/v1","denyWritePaths":["/a"]}`,
		`{"version":"agentsuite.policy/v1","denyWritePaths":["/a"],"requiredCapabilities":[]}`,
		`{"version":"agentsuite.policy/v1","denyWritePaths":["/a"],"requiredCapabilities":["unknown/v1"]}`,
		valid + ` {}`,
		valid + ` trailing`,
	}
	for _, input := range bad {
		if _, err := DecodeSuitePolicy([]byte(input)); err == nil {
			t.Errorf("accepted %q", input)
		}
	}
	if _, err := DecodeSuitePolicy([]byte(valid + " \n\t")); err != nil {
		t.Fatalf("rejected trailing whitespace: %v", err)
	}
}

func TestAdministrativePolicyDecodeIsClosed(t *testing.T) {
	valid := `{"denyWritePaths":["/admin"]}`
	validEmpty := []string{
		`{}`,
		`{"denyWritePaths":[]}`,
	}
	bad := []string{
		`null`,
		`{"denyWritePaths":null}`,
		`{"denyWritePaths":"admin"}`,
		`{"denyWritePaths":{}}`,
		`{"denyWritePaths":[1]}`,
		`{"denyWritePaths":["/admin"],"denyWritePaths":["/other"]}`,
		`{"denyWritePaths":["/admin"],"extra":true}`,
		valid + ` {}`,
		valid + ` trailing`,
	}
	if got, err := DecodeAdministrativePolicy([]byte(valid)); err != nil {
		t.Fatalf("rejected valid administrative policy: %v", err)
	} else if !equalStrings(got.DenyWritePaths, []string{"/admin"}) {
		t.Fatalf("decoded denyWritePaths = %q, want [/admin]", got.DenyWritePaths)
	}
	for _, input := range validEmpty {
		got, err := DecodeAdministrativePolicy([]byte(input))
		if err != nil {
			t.Errorf("rejected %q: %v", input, err)
		}
		if got.DenyWritePaths == nil && input != `{}` {
			t.Errorf("decoded %q as omitted rather than an explicit empty set", input)
		}
	}
	for _, input := range bad {
		if _, err := DecodeAdministrativePolicy([]byte(input)); err == nil {
			t.Errorf("accepted %q", input)
		}
	}
}

func TestEffectivePolicyUsesUTF16PathOrdering(t *testing.T) {
	suite := SuitePolicy{
		Version:              SchemaVersion,
		DenyWritePaths:       []string{"/\ue000", "/\U00010000", "/\ue000"},
		RequiredCapabilities: []string{FilesystemDenyWrite},
	}
	effective, err := Resolve(suite, AdministrativePolicy{})
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"/\U00010000", "/\ue000"}
	if !equalStrings(effective.DenyWritePaths, want) {
		t.Fatalf("Resolve path order = %q, want UTF-16 order %q", effective.DenyWritePaths, want)
	}

	reversed := EffectivePolicy{
		Version:              SchemaVersion,
		DenyWritePaths:       []string{"/\ue000", "/\U00010000", "/\ue000"},
		RequiredCapabilities: []string{FilesystemDenyWrite},
	}
	got, err := CanonicalBytes(reversed)
	if err != nil {
		t.Fatal(err)
	}
	fixture, err := os.ReadFile(filepath.Join("testdata", "effective-policy-ordering-v1.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, fixture) {
		t.Fatalf("CanonicalBytes ordering vector = %s, want %s", got, fixture)
	}
	wantDigest, err := os.ReadFile(filepath.Join("testdata", "effective-policy-ordering-v1.sha256"))
	if err != nil {
		t.Fatal(err)
	}
	if got := Digest(fixture); got != strings.TrimSpace(string(wantDigest)) {
		t.Fatalf("ordering vector digest = %s, want %s", got, strings.TrimSpace(string(wantDigest)))
	}
}

func TestPolicyDecodeRejectsUnpairedSurrogate(t *testing.T) {
	input := `{"version":"agentsuite.policy/v1","denyWritePaths":["/safe/\udcff"],"requiredCapabilities":["filesystem/deny-write/v1"]}`
	if _, err := DecodeSuitePolicy([]byte(input)); err == nil {
		t.Fatal("accepted unpaired surrogate escape")
	}
}

func TestPolicyPathLimitsApplyAtEveryBoundary(t *testing.T) {
	paths := make([]string, 4097)
	for i := range paths {
		paths[i] = fmt.Sprintf("/path/%04d", i)
	}
	admin := AdministrativePolicy{DenyWritePaths: paths}
	data, err := json.Marshal(admin)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = DecodeAdministrativePolicy(data); err == nil {
		t.Fatal("decoded oversized administrative policy")
	}
	if _, err = Resolve(sample(), admin); err == nil {
		t.Fatal("resolved oversized administrative policy")
	}
	effective := EffectivePolicy{
		Version:              SchemaVersion,
		DenyWritePaths:       paths,
		RequiredCapabilities: []string{FilesystemDenyWrite},
	}
	if _, err = CanonicalBytes(effective); err == nil {
		t.Fatal("canonicalized oversized effective policy")
	}
}

func TestTypedPolicyPathsRequireUTF8(t *testing.T) {
	for _, tc := range []struct {
		name  string
		path  string
		valid bool
	}{
		{"invalid byte", "/safe/\xff", false},
		{"truncated encoding", "/safe/\xc3", false},
		{"encoded surrogate", "/safe/\xed\xa0\x80", false},
		{"Unicode", "/safe/é", true},
		{"replacement character", "/safe/\ufffd", true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			suite := sample()
			suite.DenyWritePaths = []string{tc.path}
			effective := EffectivePolicy{
				Version:              SchemaVersion,
				DenyWritePaths:       []string{tc.path},
				RequiredCapabilities: []string{FilesystemDenyWrite},
			}
			checks := map[string]func() error{
				"Validate": func() error { return Validate(suite) },
				"Resolve suite": func() error {
					_, err := Resolve(suite, AdministrativePolicy{})
					return err
				},
				"Resolve administrative": func() error {
					_, err := Resolve(sample(), AdministrativePolicy{DenyWritePaths: []string{tc.path}})
					return err
				},
				"CanonicalBytes": func() error {
					_, err := CanonicalBytes(effective)
					return err
				},
				"Payload": func() error {
					_, err := Payload(effective)
					return err
				},
			}
			for name, check := range checks {
				if err := check(); (err == nil) != tc.valid {
					t.Errorf("%s: valid = %v, error = %v", name, tc.valid, err)
				}
			}
		})
	}
}

func TestCanonicalBytesUseJCSStringEncoding(t *testing.T) {
	policy := EffectivePolicy{
		Version:              SchemaVersion,
		DenyWritePaths:       []string{"/a&<>é"},
		RequiredCapabilities: []string{FilesystemDenyWrite},
	}
	got, err := CanonicalBytes(policy)
	if err != nil {
		t.Fatal(err)
	}
	want := `{"denyWritePaths":["/a&<>é"],"requiredCapabilities":["filesystem/deny-write/v1"],"version":"agentsuite.policy/v1"}`
	if string(got) != want {
		t.Fatalf("CanonicalBytes() = %s, want %s", got, want)
	}
}

func TestCanonicalBytesRejectsOversizedComposition(t *testing.T) {
	const limit = 4 << 20
	suite := sample()
	suite.DenyWritePaths = make([]string, 2048)
	admin := AdministrativePolicy{DenyWritePaths: make([]string, 2048)}
	padding := strings.Repeat("x", 1024)
	for i := range suite.DenyWritePaths {
		suite.DenyWritePaths[i] = fmt.Sprintf("/suite/%04d/%s", i, padding)
		admin.DenyWritePaths[i] = fmt.Sprintf("/admin/%04d/%s", i, padding)
	}
	suiteJSON, err := json.Marshal(suite)
	if err != nil {
		t.Fatal(err)
	}
	adminJSON, err := json.Marshal(admin)
	if err != nil {
		t.Fatal(err)
	}
	if len(suiteJSON) > limit || len(adminJSON) > limit {
		t.Fatal("individual inputs exceed decoder limit")
	}
	suite, err = DecodeSuitePolicy(suiteJSON)
	if err != nil {
		t.Fatal(err)
	}
	admin, err = DecodeAdministrativePolicy(adminJSON)
	if err != nil {
		t.Fatal(err)
	}
	effective, err := Resolve(suite, admin)
	if err != nil {
		t.Fatal(err)
	}
	serialized, err := json.Marshal(effective)
	if err != nil {
		t.Fatal(err)
	}
	if len(effective.DenyWritePaths) != 4096 || len(serialized) <= limit {
		t.Fatal("composition must fit path count but exceed byte limit")
	}
	if data, err := CanonicalBytes(effective); err == nil || data != nil {
		t.Errorf("oversized CanonicalBytes: returned %d bytes, error = %v", len(data), err)
	}
	if _, err := Payload(effective); err == nil {
		t.Error("Payload accepted oversized composition")
	}
}

func TestCanonicalBytesSizeBoundary(t *testing.T) {
	const limit = 4 << 20
	const prefix = `{"denyWritePaths":["/`
	const suffix = `"],"requiredCapabilities":["filesystem/deny-write/v1"],"version":"agentsuite.policy/v1"}`
	for _, size := range []int{limit - 1, limit, limit + 1} {
		t.Run(fmt.Sprint(size), func(t *testing.T) {
			effective := EffectivePolicy{
				Version:              SchemaVersion,
				DenyWritePaths:       []string{"/" + strings.Repeat("x", size-len(prefix)-len(suffix))},
				RequiredCapabilities: []string{FilesystemDenyWrite},
			}
			data, err := CanonicalBytes(effective)
			if size > limit {
				if err == nil || data != nil {
					t.Errorf("oversized CanonicalBytes: returned %d bytes, error = %v", len(data), err)
				}
				if _, err := Payload(effective); err == nil {
					t.Error("Payload accepted oversized policy")
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if len(data) != size {
				t.Fatalf("canonical size = %d, want %d", len(data), size)
			}
			payload, err := Payload(effective)
			if err != nil {
				t.Fatal(err)
			}
			if !bytes.Equal(payload.PolicyBytes, data) {
				t.Fatal("Payload changed canonical bytes")
			}
			if err := VerifyPayload(payload); err != nil {
				t.Fatalf("policy at %d bytes failed round-trip: %v", size, err)
			}
		})
	}
}

func TestCompositionCannotWeaken(t *testing.T) {
	base, err := Resolve(sample(), AdministrativePolicy{})
	if err != nil {
		t.Fatal(err)
	}
	strengthened, err := Resolve(sample(), AdministrativePolicy{DenyWritePaths: []string{"/admin"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(strengthened.DenyWritePaths) <= len(base.DenyWritePaths) {
		t.Fatal("administrative policy weakened result")
	}
}

func TestPayloadPreservesExactBytesAndCapabilities(t *testing.T) {
	effective, err := Resolve(sample(), AdministrativePolicy{})
	if err != nil {
		t.Fatal(err)
	}
	payload, err := Payload(effective)
	if err != nil {
		t.Fatal(err)
	}
	if err := VerifyPayload(payload); err != nil {
		t.Fatal(err)
	}

	cases := []ProviderPayload{
		{Version: payload.Version, PolicyBytes: append(append([]byte(nil), payload.PolicyBytes...), ' '), PolicyDigest: payload.PolicyDigest, RequiredCapabilities: payload.RequiredCapabilities},
		{Version: payload.Version, PolicyBytes: payload.PolicyBytes, PolicyDigest: payload.PolicyDigest, RequiredCapabilities: nil},
		{Version: payload.Version, PolicyBytes: payload.PolicyBytes, PolicyDigest: payload.PolicyDigest, RequiredCapabilities: []string{}},
		{Version: payload.Version, PolicyBytes: payload.PolicyBytes, PolicyDigest: payload.PolicyDigest, RequiredCapabilities: []string{"unknown/v1"}},
		{Version: payload.Version, PolicyBytes: payload.PolicyBytes, PolicyDigest: payload.PolicyDigest, RequiredCapabilities: []string{FilesystemDenyWrite, "unknown/v1"}},
	}
	for _, changed := range cases {
		if err := VerifyPayload(changed); err == nil {
			t.Errorf("accepted altered payload: %#v", changed)
		}
	}
}
