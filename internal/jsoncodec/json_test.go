package jsoncodec_test

import (
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"github.com/agent-primitives/suite/internal/jsoncodec"
)

func TestSharedCodecCanonicalBytesAndStrictDecoding(t *testing.T) {
	data, err := jsoncodec.Marshal(map[string]int{"b": 2, "a": 1})
	if err != nil || string(data) != `{"a":1,"b":2}` {
		t.Fatalf("Marshal = %s, %v", data, err)
	}
	var wire struct {
		Count  int `json:"count"`
		Number any `json:"number"`
	}
	if err := jsoncodec.Unmarshal([]byte(`{"number":443.0}`), &wire); err != nil {
		t.Fatal(err)
	}
	number, ok := wire.Number.(json.Number)
	if !ok || number.String() != "443.0" {
		t.Fatalf("number lexeme lost: %#v", wire.Number)
	}
	for _, input := range []string{
		`{"count":1,"count":2}`, `{"unknown":1}`, `{"count":null}`,
		`{"number":1} {}`, `{"number":9007199254740993}`, `{"number":"\ud800"}`,
		"{\"number\":\"\xff\"}",
	} {
		if err := jsoncodec.Unmarshal([]byte(input), &wire); err == nil {
			t.Fatalf("accepted invalid input %q", input)
		}
	}
	nested := `{"number":` + strings.Repeat("[", jsoncodec.MaxDepth+1) + "0" + strings.Repeat("]", jsoncodec.MaxDepth+1) + "}"
	if err := jsoncodec.Unmarshal([]byte(nested), &wire); !errors.Is(err, jsoncodec.ErrDepthLimit) {
		t.Fatalf("depth sentinel identity: %v", err)
	}
}

func TestSharedCodecExactValueComparison(t *testing.T) {
	left, err := jsoncodec.DecodeValue([]byte(`{"n":1.00000000000000000001}`))
	if err != nil {
		t.Fatal(err)
	}
	right, err := jsoncodec.DecodeValue([]byte(`{"n":1}`))
	if err != nil {
		t.Fatal(err)
	}
	if jsoncodec.SameExactValue(left, right) {
		t.Fatal("exact comparison rounded a fraction")
	}
	if !jsoncodec.SameExactValue(json.Number("1.0"), json.Number("1")) {
		t.Fatal("integral numeric forms should compare equal")
	}
}
