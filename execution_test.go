package agentsuite

import (
	"bytes"
	"encoding/json"
	"reflect"
	"testing"
)

func TestExecutionContractRoundTrip(t *testing.T) {
	schema := compileReferenceSchema(t, "execution.schema.json")
	for _, tc := range []struct {
		name   string
		inputs []ExecutionInput
	}{
		{"nil inputs", nil},
		{"empty inputs", []ExecutionInput{}},
		{"populated inputs", []ExecutionInput{
			{Name: "model-key", Environment: "MODEL_KEY", Secret: true},
			{Name: "model-url", Environment: "MODEL_URL", Secret: false},
		}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			contract := ExecutionContract{
				Configuration: AgentKitMountedConfig,
				Kind:          ExecutionHTTPV1,
				Protocol:      "openai-chat-v1",
				Port:          8080,
				HealthPath:    "/healthz",
				Inputs:        tc.inputs,
			}
			if err := ValidateExecutionContract(contract); err != nil {
				t.Fatal(err)
			}
			for _, encoder := range []struct {
				name    string
				marshal func(any) ([]byte, error)
			}{
				{"JSON", json.Marshal},
				{"JCS", Marshal},
			} {
				t.Run(encoder.name, func(t *testing.T) {
					data, err := encoder.marshal(contract)
					if err != nil {
						t.Fatal(err)
					}
					var decoded ExecutionContract
					if err := Unmarshal(data, &decoded); err != nil {
						t.Fatalf("decode validated contract %s: %v", data, err)
					}
					validateSchemaJSON(t, schema, string(data), true)
					if err := ValidateExecutionContract(decoded); err != nil {
						t.Fatal(err)
					}
					want := contract
					if want.Inputs == nil {
						want.Inputs = []ExecutionInput{}
					}
					if !reflect.DeepEqual(decoded, want) {
						t.Fatalf("decoded = %#v, want %#v", decoded, want)
					}
					again, err := encoder.marshal(decoded)
					if err != nil || !bytes.Equal(data, again) {
						t.Fatalf("unstable round trip: %s -> %s, error: %v", data, again, err)
					}
					if !reflect.DeepEqual(contract.Inputs, tc.inputs) {
						t.Fatal("marshaling mutated the caller's inputs")
					}
				})
			}
		})
	}
}
