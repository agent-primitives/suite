package policy

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"reflect"
	"strings"
	"testing"
)

const networkVersion = "agentsuite.policy/v2"
const networkCapability = "network/egress-allow/v1"
const networkDocument = `{"version":"agentsuite.policy/v2","network":{"egressAllow":[{"address":"9.0.0.1","protocol":"TCP","port":443},{"address":"10.0.0.2","protocol":"TCP","port":80},{"address":"9.0.0.1","protocol":"TCP","port":443}]},"requiredCapabilities":["network/egress-allow/v1"]}`
const networkCanonical = `{"network":{"egressAllow":[{"address":"10.0.0.2","port":80,"protocol":"TCP"},{"address":"9.0.0.1","port":443,"protocol":"TCP"}]},"requiredCapabilities":["network/egress-allow/v1"],"version":"agentsuite.policy/v2"}`

func networkTestJSON(t *testing.T, value any) []byte {
	t.Helper()
	data, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	return data
}

func networkSample() SuitePolicy {
	return SuitePolicy{Version: SchemaVersionV2, Network: &NetworkPolicy{EgressAllow: []NetworkEndpoint{
		{Address: "9.0.0.1", Protocol: "TCP", Port: 443},
		{Address: "10.0.0.2", Protocol: "TCP", Port: 80},
		{Address: "9.0.0.1", Protocol: "TCP", Port: 443},
	}}, RequiredCapabilities: []string{NetworkEgressAllow}}
}

func TestNetworkDecodeResolvePayload(t *testing.T) {
	suite, err := DecodeSuitePolicy([]byte(networkDocument))
	if err != nil {
		t.Fatalf("decode v2: %v", err)
	}
	effective, err := Resolve(suite, AdministrativePolicy{})
	if err != nil {
		t.Fatal(err)
	}
	data, err := CanonicalBytes(effective)
	if err != nil {
		t.Fatal(err)
	}
	if string(data) != networkCanonical {
		t.Fatalf("canonical = %s, want %s", data, networkCanonical)
	}
	payload, err := Payload(effective)
	if err != nil {
		t.Fatal(err)
	}
	if payload.Version != networkVersion || !bytes.Equal(payload.PolicyBytes, data) {
		t.Fatalf("payload changed version or bytes: %#v", payload)
	}
	if err := VerifyPayload(payload); err != nil {
		t.Fatal(err)
	}
}

func TestNetworkDecodeClosedAndRequired(t *testing.T) {
	endpoint := `{"address":"10.0.0.2","protocol":"TCP","port":443}`
	wrap := func(value string) string {
		return `{"version":"agentsuite.policy/v2","network":{"egressAllow":[` + value + `]},"requiredCapabilities":["network/egress-allow/v1"]}`
	}
	badEndpoints := []string{
		`null`, `{}`, `{"address":"10.0.0.2","port":443}`, `{"protocol":"TCP","port":443}`, `{"address":"10.0.0.2","protocol":"TCP"}`,
		strings.Replace(endpoint, `"10.0.0.2"`, `null`, 1), strings.Replace(endpoint, `"TCP"`, `null`, 1), strings.Replace(endpoint, `443`, `null`, 1),
		strings.Replace(endpoint, `443`, `"443"`, 1), strings.Replace(endpoint, `443`, `443.5`, 1), strings.Replace(endpoint, `443`, `4.435e2`, 1),
		strings.Replace(endpoint, `443`, `443.0000000000000000000001`, 1), strings.Replace(endpoint, `443`, `9007199254740993`, 1),
		strings.Replace(endpoint, `443`, `0`, 1), strings.Replace(endpoint, `443`, `65536`, 1), strings.Replace(endpoint, `443`, `-1`, 1),
		strings.Replace(endpoint, `443`, `[80,443]`, 1), strings.Replace(endpoint, `"TCP"`, `"UDP"`, 1), strings.Replace(endpoint, `"TCP"`, `"tcp"`, 1),
		strings.Replace(endpoint, `}`, `,"extra":true}`, 1), strings.Replace(endpoint, `}`, `,"port":80}`, 1),
	}
	for _, address := range []string{"example.com", "10.0.0.0/24", "::1", "::ffff:10.0.0.2", "010.0.0.2", "10.0.0.2 ", "10.0.0", "10.0.0.256", "*", "10.0.0.1-10.0.0.2", "10.0.0.2:443"} {
		badEndpoints = append(badEndpoints, strings.Replace(endpoint, "10.0.0.2", address, 1))
	}
	bad := []string{
		`null`, `{}`, `{"version":"agentsuite.policy/v2","requiredCapabilities":["network/egress-allow/v1"]}`,
		`{"version":"agentsuite.policy/v2","network":null,"requiredCapabilities":["network/egress-allow/v1"]}`,
		`{"version":"agentsuite.policy/v2","network":{},"requiredCapabilities":["network/egress-allow/v1"]}`,
		`{"version":"agentsuite.policy/v2","network":{"egressAllow":null},"requiredCapabilities":["network/egress-allow/v1"]}`,
		strings.Replace(networkDocument, `"network":{`, `"network":{"extra":true,`, 1),
		strings.Replace(networkDocument, `"version":`, `"denyWritePaths":null,"version":`, 1),
		strings.Replace(networkDocument, `"version":`, `"denyWritePaths":[],"version":`, 1),
		strings.Replace(networkDocument, `"version":`, `"extra":true,"version":`, 1),
		strings.Replace(networkDocument, `"version":`, `"Version":"agentsuite.policy/v2","version":`, 1),
		networkDocument + `{}`, networkDocument + ` trailing`,
		strings.Replace(networkDocument, `"requiredCapabilities":["network/egress-allow/v1"]`, `"requiredCapabilities":null`, 1),
		strings.Replace(networkDocument, `"requiredCapabilities":["network/egress-allow/v1"]`, `"requiredCapabilities":[]`, 1),
		strings.Replace(networkDocument, `,"requiredCapabilities":["network/egress-allow/v1"]`, ``, 1),
		strings.Replace(networkDocument, `"network/egress-allow/v1"`, `"filesystem/deny-write/v1"`, 1),
		strings.Replace(networkDocument, `"network/egress-allow/v1"`, `"network/egress-allow/v1","network/egress-allow/v1"`, 1),
		strings.Replace(networkDocument, `"network/egress-allow/v1"`, `"network/egress-allow/v1","unknown/v1"`, 1),
	}
	for _, value := range badEndpoints {
		bad = append(bad, wrap(value))
	}
	for _, input := range bad {
		if _, err := DecodeSuitePolicy([]byte(input)); err == nil {
			t.Errorf("accepted invalid v2: %s", input)
		}
	}
	for _, address := range []string{"0.0.0.0", "127.0.0.1", "169.254.1.2", "224.0.0.1", "255.255.255.255", "192.0.2.1"} {
		for _, port := range []string{"1", "65535"} {
			input := wrap(strings.Replace(strings.Replace(endpoint, "10.0.0.2", address, 1), "443", port, 1))
			if _, err := DecodeSuitePolicy([]byte(input)); err != nil {
				t.Errorf("literal address class/port refused: %s: %v", input, err)
			}
		}
	}
	denyAll := `{"version":"agentsuite.policy/v2","network":{"egressAllow":[]},"requiredCapabilities":["network/egress-allow/v1"]}`
	if _, err := DecodeSuitePolicy([]byte(denyAll + " \n\t")); err != nil {
		t.Errorf("deny-all with trailing whitespace: %v", err)
	}
}

func TestNetworkIntegralPortLexemes(t *testing.T) {
	for _, port := range []string{"443", "443.0", "4.43e2", "443.0000000000000000000000000000000000000000"} {
		input := `{"version":"agentsuite.policy/v2","network":{"egressAllow":[{"address":"10.0.0.2","protocol":"TCP","port":` + port + `}]},"requiredCapabilities":["network/egress-allow/v1"]}`
		suite, err := DecodeSuitePolicy([]byte(input))
		if err != nil || suite.Network.EgressAllow[0].Port != 443 {
			t.Fatalf("suite integral port %s: %#v, %v", port, suite, err)
		}
		adminInput := `{"network":{"egressAllow":[{"address":"10.0.0.2","protocol":"TCP","port":` + port + `}]}}`
		admin, err := DecodeAdministrativePolicyForVersion([]byte(adminInput), SchemaVersionV2)
		if err != nil || admin.Network.EgressAllow[0].Port != 443 {
			t.Fatalf("admin integral port %s: %#v, %v", port, admin, err)
		}
	}
}

func TestNetworkPortsRejectRoundedFractions(t *testing.T) {
	for _, port := range []string{"443.0000000000000000000001", "442.9999999999999999999999", "1.0000000000000000000001", "65535.0000000000000000001", "1e-1000000000", "1e1000000000"} {
		endpoint := `{"address":"10.0.0.2","protocol":"TCP","port":` + port + `}`
		suite := `{"version":"agentsuite.policy/v2","network":{"egressAllow":[` + endpoint + `]},"requiredCapabilities":["network/egress-allow/v1"]}`
		if _, err := DecodeSuitePolicy([]byte(suite)); err == nil {
			t.Errorf("suite accepted noninteger/out-of-range port %s", port)
		}
		if _, err := DecodeAdministrativePolicyForVersion([]byte(`{"network":{"egressAllow":[`+endpoint+`]}}`), SchemaVersionV2); err == nil {
			t.Errorf("admin accepted noninteger/out-of-range port %s", port)
		}
	}
}

func TestNetworkAdministration(t *testing.T) {
	for name, tc := range map[string]struct {
		input string
		want  []NetworkEndpoint
	}{
		"omitted":                {`{}`, []NetworkEndpoint{{Address: "10.0.0.2", Protocol: "TCP", Port: 80}, {Address: "9.0.0.1", Protocol: "TCP", Port: 443}}},
		"deny all":               {`{"network":{"egressAllow":[]}}`, []NetworkEndpoint{}},
		"intersection not union": {`{"network":{"egressAllow":[{"address":"9.0.0.1","protocol":"TCP","port":443},{"address":"10.0.0.2","protocol":"TCP","port":443},{"address":"8.8.8.8","protocol":"TCP","port":53}]}}`, []NetworkEndpoint{{Address: "9.0.0.1", Protocol: "TCP", Port: 443}}},
		"disjoint":               {`{"network":{"egressAllow":[{"address":"8.8.8.8","protocol":"TCP","port":53}]}}`, []NetworkEndpoint{}},
	} {
		t.Run(name, func(t *testing.T) {
			admin, err := DecodeAdministrativePolicyForVersion([]byte(tc.input), SchemaVersionV2)
			if err != nil {
				t.Fatal(err)
			}
			if (admin.Network == nil) != (name == "omitted") {
				t.Fatal("omitted and explicit restrictions conflated")
			}
			effective, err := Resolve(networkSample(), admin)
			if err != nil {
				t.Fatal(err)
			}
			if !reflect.DeepEqual(effective.Network.EgressAllow, tc.want) {
				t.Fatalf("intersection = %#v, want %#v", effective.Network.EgressAllow, tc.want)
			}
		})
	}
	for _, input := range []string{`null`, `{"network":null}`, `{"network":{}}`, `{"network":{"egressAllow":null}}`, `{"network":{"egressAllow":[null]}}`, `{"denyWritePaths":null}`, `{"denyWritePaths":[]}`, `{"extra":true}`, `{"network":{"egressAllow":[],"extra":true}}`, `{"network":{"egressAllow":[],"egressAllow":[]}}`, `{} {}`, `{"network":{"egressAllow":[{"address":"hostname","protocol":"TCP","port":443}]}}`} {
		if _, err := DecodeAdministrativePolicyForVersion([]byte(input), SchemaVersionV2); err == nil {
			t.Errorf("accepted v2 admin %s", input)
		}
	}
	if _, err := DecodeAdministrativePolicyForVersion([]byte(`{}`), "future"); err == nil {
		t.Error("accepted unknown admin profile")
	}
	for _, input := range []string{`{}`, `{"denyWritePaths":[]}`, `{"denyWritePaths":["/a"]}`} {
		legacy, err := DecodeAdministrativePolicy([]byte(input))
		if err != nil {
			t.Fatal(err)
		}
		versioned, err := DecodeAdministrativePolicyForVersion([]byte(input), SchemaVersion)
		if err != nil || !reflect.DeepEqual(legacy, versioned) {
			t.Fatalf("v1 admin behavior changed: %#v, %v", versioned, err)
		}
	}
	for _, decode := range []func([]byte) (AdministrativePolicy, error){
		DecodeAdministrativePolicy,
		func(data []byte) (AdministrativePolicy, error) {
			return DecodeAdministrativePolicyForVersion(data, SchemaVersion)
		},
	} {
		if _, err := decode([]byte(`{"denyWritePaths":null}`)); err == nil {
			t.Error("accepted explicit-null v1 administrative paths")
		}
	}
}

func TestNetworkTypedValidation(t *testing.T) {
	if SchemaVersion != "agentsuite.policy/v1" || SchemaVersionV2 != networkVersion || NetworkEgressAllow != networkCapability {
		t.Fatal("public constants changed")
	}
	invalid := []SuitePolicy{}
	for _, endpoint := range []NetworkEndpoint{
		{}, {Address: "example.com", Protocol: "TCP", Port: 443}, {Address: "::ffff:10.0.0.2", Protocol: "TCP", Port: 443},
		{Address: "10.0.0.2", Protocol: "UDP", Port: 443}, {Address: "10.0.0.2", Protocol: "TCP", Port: 0},
		{Address: "10.0.0.2", Protocol: "TCP", Port: 65536}, {Address: "10.0.0.2\xff", Protocol: "TCP", Port: 443},
	} {
		p := networkSample()
		p.Network = &NetworkPolicy{EgressAllow: []NetworkEndpoint{endpoint}}
		invalid = append(invalid, p)
		if _, err := Resolve(networkSample(), AdministrativePolicy{Network: p.Network}); err == nil {
			t.Errorf("accepted typed admin endpoint %#v", endpoint)
		}
	}
	for _, network := range []*NetworkPolicy{nil, {}} {
		p := networkSample()
		p.Network = network
		invalid = append(invalid, p)
	}
	for _, caps := range [][]string{nil, {}, {FilesystemDenyWrite}, {NetworkEgressAllow, NetworkEgressAllow}} {
		p := networkSample()
		p.RequiredCapabilities = caps
		invalid = append(invalid, p)
	}
	for _, paths := range [][]string{{}, {"/a"}} {
		p := networkSample()
		p.DenyWritePaths = paths
		invalid = append(invalid, p)
		if _, err := Resolve(networkSample(), AdministrativePolicy{DenyWritePaths: paths}); err == nil {
			t.Errorf("accepted v2 typed filesystem admin %#v", paths)
		}
	}
	v1 := sample()
	v1.Network = &NetworkPolicy{EgressAllow: []NetworkEndpoint{}}
	invalid = append(invalid, v1)
	if _, err := Resolve(sample(), AdministrativePolicy{Network: &NetworkPolicy{EgressAllow: []NetworkEndpoint{}}}); err == nil {
		t.Error("accepted v1 typed network admin")
	}
	if _, err := Resolve(networkSample(), AdministrativePolicy{Network: &NetworkPolicy{}}); err == nil {
		t.Error("accepted nil typed admin list")
	}
	for i, p := range invalid {
		t.Run(fmt.Sprint(i), func(t *testing.T) {
			if err := Validate(p); err == nil {
				t.Error("Validate accepted invalid typed profile")
			}
			if _, err := Resolve(p, AdministrativePolicy{}); err == nil {
				t.Error("Resolve accepted invalid typed profile")
			}
			effective := EffectivePolicy(p)
			if _, err := CanonicalBytes(effective); err == nil {
				t.Error("CanonicalBytes accepted invalid typed profile")
			}
			if _, err := Payload(effective); err == nil {
				t.Error("Payload accepted invalid typed profile")
			}
		})
	}
}

func TestNetworkNormalizationDoesNotAlias(t *testing.T) {
	suite := networkSample()
	suite.Network.EgressAllow = append(suite.Network.EgressAllow, NetworkEndpoint{Address: "10.0.0.2", Protocol: "TCP", Port: 443}, NetworkEndpoint{Address: "10.0.0.2", Protocol: "TCP", Port: 9})
	admin := AdministrativePolicy{Network: &NetworkPolicy{EgressAllow: append([]NetworkEndpoint(nil), suite.Network.EgressAllow...)}}
	beforeSuite := networkTestJSON(t, suite)
	beforeAdmin := networkTestJSON(t, admin)
	effective, err := Resolve(suite, admin)
	if err != nil {
		t.Fatal(err)
	}
	want := []NetworkEndpoint{{Address: "10.0.0.2", Protocol: "TCP", Port: 9}, {Address: "10.0.0.2", Protocol: "TCP", Port: 80}, {Address: "10.0.0.2", Protocol: "TCP", Port: 443}, {Address: "9.0.0.1", Protocol: "TCP", Port: 443}}
	if !reflect.DeepEqual(effective.Network.EgressAllow, want) {
		t.Fatalf("normalization = %#v, want %#v", effective.Network.EgressAllow, want)
	}
	// Canonicalization must normalize its own copy, too.
	unnormalized := EffectivePolicy{Version: suite.Version, Network: suite.Network, RequiredCapabilities: suite.RequiredCapabilities}
	if _, err := CanonicalBytes(unnormalized); err != nil {
		t.Fatal(err)
	}
	afterSuite := networkTestJSON(t, suite)
	afterAdmin := networkTestJSON(t, admin)
	if !bytes.Equal(beforeSuite, afterSuite) || !bytes.Equal(beforeAdmin, afterAdmin) {
		t.Fatal("resolution or canonicalization mutated inputs")
	}
	suite.Network.EgressAllow[0].Port = 1
	admin.Network.EgressAllow[0].Address = "1.1.1.1"
	suite.RequiredCapabilities[0] = "changed"
	if !reflect.DeepEqual(effective.Network.EgressAllow, want) || effective.RequiredCapabilities[0] != NetworkEgressAllow {
		t.Fatal("effective result aliases input")
	}
	payload, err := Payload(effective)
	if err != nil {
		t.Fatal(err)
	}
	effective.RequiredCapabilities[0] = "changed"
	effective.Network.EgressAllow[0].Port = 2
	if err := VerifyPayload(payload); err != nil {
		t.Fatalf("payload aliases effective policy: %v", err)
	}
	shared := networkSample()
	neutral, err := Resolve(shared, AdministrativePolicy{})
	if err != nil {
		t.Fatal(err)
	}
	other, err := Resolve(shared, AdministrativePolicy{})
	if err != nil {
		t.Fatal(err)
	}
	neutral.Network.EgressAllow[0].Port = 1
	if other.Network.EgressAllow[0].Port != 80 || shared.Network.EgressAllow[1].Port != 80 {
		t.Fatal("neutral result aliases inputs or other results")
	}
}

func TestNetworkListLimits(t *testing.T) {
	for _, size := range []int{4096, 4097} {
		t.Run(fmt.Sprint(size), func(t *testing.T) {
			p := networkSample()
			p.Network.EgressAllow = make([]NetworkEndpoint, size)
			for i := range p.Network.EgressAllow {
				// Duplicate raw entries count toward the limit, before normalization.
				p.Network.EgressAllow[i] = NetworkEndpoint{Address: "10.0.0.2", Protocol: "TCP", Port: 443}
			}
			admin := AdministrativePolicy{Network: p.Network}
			effective := EffectivePolicy{Version: p.Version, Network: p.Network, RequiredCapabilities: p.RequiredCapabilities}
			checks := map[string]func() error{
				"validate":     func() error { return Validate(p) },
				"suite decode": func() error { _, err := DecodeSuitePolicy(networkTestJSON(t, p)); return err },
				"admin decode": func() error {
					data := networkTestJSON(t, admin)
					_, err := DecodeAdministrativePolicyForVersion(data, SchemaVersionV2)
					return err
				},
				"resolve suite": func() error { _, err := Resolve(p, AdministrativePolicy{}); return err },
				"resolve admin": func() error { _, err := Resolve(networkSample(), admin); return err },
				"canonical":     func() error { _, err := CanonicalBytes(effective); return err },
				"payload":       func() error { _, err := Payload(effective); return err },
			}
			for name, check := range checks {
				if err := check(); (err == nil) != (size <= 4096) {
					t.Errorf("%s at %d entries: %v", name, size, err)
				}
			}
		})
	}
	oversized := []byte(networkDocument + strings.Repeat(" ", 4<<20))
	if _, err := DecodeSuitePolicy(oversized); err == nil {
		t.Error("suite decode accepted oversized document")
	}
	if _, err := DecodeAdministrativePolicyForVersion([]byte(`{}`+strings.Repeat(" ", 4<<20)), SchemaVersionV2); err == nil {
		t.Error("admin decode accepted oversized document")
	}
	payload := ProviderPayload{Version: SchemaVersionV2, PolicyBytes: oversized, PolicyDigest: Digest(oversized), RequiredCapabilities: []string{NetworkEgressAllow}}
	if err := VerifyPayload(payload); err == nil {
		t.Error("payload accepted oversized policy bytes")
	}
}

func TestNetworkGoldenVectors(t *testing.T) {
	for _, name := range []string{"effective-policy-v2", "effective-policy-v2-deny-all"} {
		t.Run(name, func(t *testing.T) {
			data, err := os.ReadFile("testdata/" + name + ".json")
			if err != nil {
				t.Fatal(err)
			}
			goldenDigest, err := os.ReadFile("testdata/" + name + ".sha256")
			if err != nil {
				t.Fatal(err)
			}
			// Independent framing: do not derive expected vectors through Digest.
			framed := append([]byte("agentsuite-effective-policy\x00v1\x00"), make([]byte, 8)...)
			binary.BigEndian.PutUint64(framed[len(framed)-8:], uint64(len(data)))
			sum := sha256.Sum256(append(framed, data...))
			wantDigest := "sha256:" + hex.EncodeToString(sum[:])
			if strings.TrimSpace(string(goldenDigest)) != wantDigest || Digest(data) != wantDigest {
				t.Fatalf("golden digest differs from independent framing: %s", wantDigest)
			}
			suite := networkSample()
			if strings.HasSuffix(name, "deny-all") {
				suite.Network.EgressAllow = []NetworkEndpoint{}
			}
			effective, err := Resolve(suite, AdministrativePolicy{})
			if err != nil {
				t.Fatal(err)
			}
			canonical, err := CanonicalBytes(effective)
			if err != nil {
				t.Fatal(err)
			}
			if !bytes.Equal(data, canonical) {
				t.Fatalf("golden canonical bytes differ: %s", canonical)
			}
			if err := VerifyPayload(ProviderPayload{Version: SchemaVersionV2, PolicyBytes: data, PolicyDigest: wantDigest, RequiredCapabilities: []string{NetworkEgressAllow}}); err != nil {
				t.Fatal(err)
			}
		})
	}
}

func TestNetworkV1WireRemainsClosed(t *testing.T) {
	valid := `{"version":"agentsuite.policy/v1","denyWritePaths":["/a"],"requiredCapabilities":["filesystem/deny-write/v1"]}`
	for _, value := range []string{`null`, `{}`, `{"egressAllow":[]}`} {
		if _, err := DecodeSuitePolicy([]byte(strings.Replace(valid, `"version":`, `"network":`+value+`,"version":`, 1))); err == nil {
			t.Errorf("v1 accepted network %s", value)
		}
		if _, err := DecodeAdministrativePolicy([]byte(`{"network":` + value + `}`)); err == nil {
			t.Errorf("legacy admin accepted network %s", value)
		}
	}
}

func TestNetworkPayloadVersionMismatch(t *testing.T) {
	v1, err := Resolve(sample(), AdministrativePolicy{})
	if err != nil {
		t.Fatal(err)
	}
	v1Payload, err := Payload(v1)
	if err != nil {
		t.Fatal(err)
	}
	v2, err := Resolve(networkSample(), AdministrativePolicy{})
	if err != nil {
		t.Fatal(err)
	}
	v2Payload, err := Payload(v2)
	if err != nil {
		t.Fatal(err)
	}
	// Both inner policies and outer profiles are independently valid.
	v1Payload.Version = SchemaVersionV2
	v1Payload.RequiredCapabilities = []string{NetworkEgressAllow}
	v2Payload.Version = SchemaVersion
	v2Payload.RequiredCapabilities = []string{FilesystemDenyWrite}
	for _, p := range []ProviderPayload{v1Payload, v2Payload} {
		if err := VerifyPayload(p); err == nil || !strings.Contains(err.Error(), "version does not match") {
			t.Fatalf("expected explicit version mismatch, got %v", err)
		}
	}
}

func TestNetworkPayloadTampering(t *testing.T) {
	base := ProviderPayload{Version: networkVersion, PolicyBytes: []byte(networkCanonical), PolicyDigest: Digest([]byte(networkCanonical)), RequiredCapabilities: []string{networkCapability}}
	if err := VerifyPayload(base); err != nil {
		t.Fatalf("valid v2 payload: %v", err)
	}
	cases := map[string]ProviderPayload{}
	for _, version := range []string{"future", SchemaVersion} {
		p := base
		p.Version = version
		cases["outer "+version] = p
	}
	for _, caps := range [][]string{nil, {}, {FilesystemDenyWrite}, {networkCapability, "extra"}, {networkCapability, networkCapability}} {
		p := base
		p.RequiredCapabilities = caps
		encoded := networkTestJSON(t, caps)
		cases["caps "+string(encoded)] = p
	}
	for name, data := range map[string]string{
		"whitespace":                    networkCanonical + " ",
		"unsorted and duplicate":        networkDocument,
		"inner version":                 strings.Replace(networkCanonical, networkVersion, SchemaVersion, 1),
		"inner caps":                    strings.Replace(networkCanonical, networkCapability, FilesystemDenyWrite, 1),
		"noncanonical integer decimal":  strings.Replace(networkCanonical, `"port":443`, `"port":443.0`, 1),
		"noncanonical integer exponent": strings.Replace(networkCanonical, `"port":443`, `"port":4.43e2`, 1),
		"mixed fields":                  strings.Replace(networkCanonical, `"network":`, `"denyWritePaths":null,"network":`, 1),
		"null list":                     strings.Replace(networkCanonical, `[{"address":"10.0.0.2","port":80,"protocol":"TCP"},{"address":"9.0.0.1","port":443,"protocol":"TCP"}]`, `null`, 1),
	} {
		p := base
		p.PolicyBytes = []byte(data)
		p.PolicyDigest = Digest(p.PolicyBytes)
		cases[name] = p
	}
	p := base
	p.PolicyDigest = "sha256:" + strings.Repeat("0", 64)
	cases["digest"] = p
	p = base
	p.PolicyBytes = append(append([]byte(nil), p.PolicyBytes...), ' ')
	cases["bytes without digest update"] = p
	for name, payload := range cases {
		t.Run(name, func(t *testing.T) {
			if err := VerifyPayload(payload); err == nil {
				t.Fatal("accepted tampered payload")
			}
		})
	}
}
