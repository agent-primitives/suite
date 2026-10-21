package artifact

import (
	"strings"
	"testing"
)

const networkEndpointJSON = `{"address":"192.0.2.10","protocol":"TCP","port":443}`
const networkPolicyJSON = `{"version":"agentsuite.policy/v2","network":{"egressAllow":[` + networkEndpointJSON + `]},"requiredCapabilities":["network/egress-allow/v1"]}`

func TestNetworkPolicyV2ReferenceSchema(t *testing.T) {
	schema := compileReferenceSchema(t, "policy-v2.schema.json")
	for _, document := range []string{
		networkPolicyJSON,
		strings.Replace(networkPolicyJSON, networkEndpointJSON, networkEndpointJSON+","+networkEndpointJSON, 1),
		strings.Replace(networkPolicyJSON, networkEndpointJSON, "", 1),
		strings.Replace(networkPolicyJSON, `"port":443`, `"port":1`, 1),
		strings.Replace(networkPolicyJSON, `"port":443`, `"port":65535`, 1),
	} {
		validateSchemaJSON(t, schema, document, true)
	}
	for _, tc := range []struct{ name, from, to string }{
		{"version", "agentsuite.policy/v2", "agentsuite.policy/v1"},
		{"hostname", "192.0.2.10", "example.invalid"},
		{"CIDR", "192.0.2.10", "192.0.2.10/32"},
		{"address range", "192.0.2.10", "192.0.2.10-192.0.2.20"},
		{"IPv6", "192.0.2.10", "2001:db8::1"},
		{"mapped IPv6", "192.0.2.10", "::ffff:192.0.2.10"},
		{"leading zeros", "192.0.2.10", "192.000.2.10"},
		{"octet overflow", "192.0.2.10", "256.0.2.10"},
		{"UDP", `"TCP"`, `"UDP"`},
		{"protocol case", `"TCP"`, `"tcp"`},
		{"zero port", `"port":443`, `"port":0`},
		{"negative port", `"port":443`, `"port":-1`},
		{"large port", `"port":443`, `"port":65536`},
		{"fractional port", `"port":443`, `"port":443.5`},
		{"named port", `"port":443`, `"port":"https"`},
		{"range port", `"port":443`, `"port":"440-450"`},
		{"range object", `"port":443`, `"port":{"from":440,"to":450}`},
		{"missing port", `,"port":443`, ``},
		{"missing protocol", `,"protocol":"TCP"`, ``},
		{"missing address", `"address":"192.0.2.10",`, ``},
		{"null port", `"port":443`, `"port":null`},
		{"null network", `{"egressAllow":[` + networkEndpointJSON + `]}`, `null`},
		{"missing list", `"egressAllow":[` + networkEndpointJSON + `]`, ``},
		{"null list", `[` + networkEndpointJSON + `]`, `null`},
		{"unknown capability", "network/egress-allow/v1", "tools/allow/v1"},
		{"empty capabilities", `["network/egress-allow/v1"]`, `[]`},
		{"duplicate capabilities", `["network/egress-allow/v1"]`, `["network/egress-allow/v1","network/egress-allow/v1"]`},
		{"unknown endpoint field", `"port":443`, `"port":443,"endPort":450`},
		{"unknown network field", `"egressAllow":`, `"dns":true,"egressAllow":`},
		{"filesystem field", `"version":`, `"denyWritePaths":[],"version":`},
		{"null filesystem field", `"version":`, `"denyWritePaths":null,"version":`},
		{"unknown root field", `"version":`, `"extra":true,"version":`},
	} {
		t.Run(tc.name, func(t *testing.T) {
			validateSchemaJSON(t, schema, strings.Replace(networkPolicyJSON, tc.from, tc.to, 1), false)
		})
	}
	tooMany := strings.Replace(networkPolicyJSON, networkEndpointJSON, strings.Repeat(networkEndpointJSON+",", 4096)+networkEndpointJSON, 1)
	validateSchemaJSON(t, schema, tooMany, false)
}

func TestNetworkAdministrativeV2ReferenceSchema(t *testing.T) {
	schema := compileReferenceSchema(t, "administrative-policy-v2.schema.json")
	for _, document := range []string{
		`{}`,
		`{"network":{"egressAllow":[]}}`,
		`{"network":{"egressAllow":[` + networkEndpointJSON + `]}}`,
		`{"network":{"egressAllow":[` + networkEndpointJSON + `,` + networkEndpointJSON + `]}}`,
	} {
		validateSchemaJSON(t, schema, document, true)
	}
	for _, document := range []string{
		`null`, `[]`, `{"network":null}`, `{"network":{}}`, `{"network":{"egressAllow":null}}`,
		`{"denyWritePaths":[]}`, `{"denyWritePaths":null}`, `{"extra":true}`,
		`{"network":{"egressAllow":[],"extra":true}}`,
		`{"network":{"egressAllow":[{"address":"192.0.2.10","protocol":"UDP","port":443}]}}`,
	} {
		validateSchemaJSON(t, schema, document, false)
	}
}
