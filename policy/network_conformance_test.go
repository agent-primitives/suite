package policy

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/google/jsonschema-go/jsonschema"
)

func policySchema(t *testing.T, name string) *jsonschema.Resolved {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "schema", name))
	if err != nil {
		t.Fatal(err)
	}
	var schema jsonschema.Schema
	if err := json.Unmarshal(data, &schema); err != nil {
		t.Fatal(err)
	}
	resolved, err := schema.Resolve(nil)
	if err != nil {
		t.Fatal(err)
	}
	return resolved
}

func TestNetworkSchemaCodecAgreement(t *testing.T) {
	for _, admin := range []bool{false, true} {
		name := "policy-v2.schema.json"
		if admin {
			name = "administrative-policy-v2.schema.json"
		}
		schema := policySchema(t, name)
		for _, tc := range []struct {
			endpoint string
			valid    bool
		}{
			{`{"address":"192.0.2.10","protocol":"TCP","port":443}`, true},
			{`{"address":"192.0.2.10","protocol":"TCP","port":443.0}`, true},
			{`{"address":"192.0.2.10","protocol":"TCP","port":4.43e2}`, true},
			{`{"address":"192.0.2.10","protocol":"TCP","port":"443"}`, false},
			{`{"address":"192.0.2.10","protocol":"TCP","port":443.5}`, false},
			{`{"address":"192.0.2.10","protocol":"UDP","port":443}`, false},
			{`{"address":"192.0.2.10/32","protocol":"TCP","port":443}`, false},
			{`{"address":"example.invalid","protocol":"TCP","port":443}`, false},
			{`{"address":"192.0.2.10","protocol":"TCP","port":443,"endPort":450}`, false},
			{`{"address":"192.0.2.10","protocol":"TCP"}`, false},
			{`null`, false},
		} {
			document := `{"network":{"egressAllow":[` + tc.endpoint + `]}}`
			if !admin {
				document = `{"version":"agentsuite.policy/v2","requiredCapabilities":["network/egress-allow/v1"],"network":{"egressAllow":[` + tc.endpoint + `]}}`
			}
			var value any
			if err := json.Unmarshal([]byte(document), &value); err != nil {
				t.Fatal(err)
			}
			schemaErr := schema.Validate(value)
			var codecErr error
			if admin {
				_, codecErr = DecodeAdministrativePolicyForVersion([]byte(document), SchemaVersionV2)
			} else {
				_, codecErr = DecodeSuitePolicy([]byte(document))
			}
			if (schemaErr == nil) != tc.valid || (codecErr == nil) != tc.valid {
				t.Errorf("admin=%v endpoint=%s: expected valid=%v; schema=%v codec=%v", admin, tc.endpoint, tc.valid, schemaErr, codecErr)
			}
		}
	}
	for _, name := range []string{"effective-policy-v2.json", "effective-policy-v2-deny-all.json"} {
		data, err := os.ReadFile(filepath.Join("testdata", name))
		if err != nil {
			t.Fatal(err)
		}
		var value any
		if err := json.Unmarshal(data, &value); err != nil {
			t.Fatal(err)
		}
		if err := policySchema(t, "policy-v2.schema.json").Validate(value); err != nil {
			t.Fatalf("vector %s rejected by reference schema: %v", name, err)
		}
	}
}

func TestNetworkAddressDiagnosticsDoNotEchoInput(t *testing.T) {
	const marker = "operand-must-not-be-echoed.invalid"
	p := networkSample()
	p.Network.EgressAllow[0].Address = marker + "\x1b[31m"
	data, err := json.Marshal(p)
	if err != nil {
		t.Fatal(err)
	}
	checks := map[string]func() error{
		"typed":   func() error { return Validate(p) },
		"decoded": func() error { _, err := DecodeSuitePolicy(data); return err },
	}
	for name, check := range checks {
		err := check()
		if err == nil || strings.Contains(err.Error(), marker) || strings.ContainsRune(err.Error(), '\x1b') {
			t.Errorf("%s: missing refusal or echoed address operand: %v", name, err)
		}
	}
}
