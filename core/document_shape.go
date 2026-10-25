package core

import (
	"encoding/json"
	"fmt"
	"strings"
)

// Authored document fields are non-null. Keep this at their boundaries, not in
// jsoncodec: OCI metadata and referenced literal JSON schemas have other rules.
// Agent extension items are left to the existing checks because their schema
// intentionally does not constrain item shapes.
func requireNonNullFields(fields map[string]json.RawMessage) error {
	for name, raw := range fields {
		var value any
		if err := json.Unmarshal(raw, &value); err != nil {
			return err
		}
		if err := requireNonNullValue(value, "/"+pointerKey(name)); err != nil {
			return err
		}
	}
	return nil
}

func pointerKey(value string) string {
	return strings.ReplaceAll(strings.ReplaceAll(value, "~", "~0"), "/", "~1")
}

func requireNonNullValue(value any, pointer string) error {
	// This projection is only for presence: never reserialize its numbers.
	switch v := value.(type) {
	case nil:
		return fmt.Errorf("%s must not be null", pointer)
	case map[string]any:
		for key, child := range v {
			if err := requireNonNullValue(child, pointer+"/"+pointerKey(key)); err != nil {
				return err
			}
		}
	case []any:
		for i, child := range v {
			if err := requireNonNullValue(child, fmt.Sprintf("%s/%d", pointer, i)); err != nil {
				return err
			}
		}
	}
	return nil
}

func (a *Agent) UnmarshalJSON(data []byte) error {
	type wire Agent
	value := wire(*a)
	if err := Unmarshal(data, &value); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		return err
	}
	if isJSONNull(fields["extensions"]) {
		return fmt.Errorf("agent extensions must not be null")
	}
	// Leave extension items and existing policy/eval null checks with their
	// established decoder/graph boundaries.
	for _, key := range []string{"extensions", "policy", "evals"} {
		delete(fields, key)
	}
	if err := requireNonNullFields(fields); err != nil {
		return err
	}
	*a = Agent(value)
	return nil
}

// Shared Platform also describes OCI metadata. Only authored roles forbid the
// variant property entirely, including a present empty string.
func requireAuthoredPlatform(raw json.RawMessage) error {
	if len(raw) == 0 {
		return nil
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(raw, &fields); err != nil {
		return err
	}
	if _, present := fields["variant"]; present {
		return fmt.Errorf("authored platform must not declare variant")
	}
	return nil
}

func requireVariantPresence(raw json.RawMessage) error {
	if len(raw) == 0 {
		return nil
	}
	var variants []struct {
		Platform    json.RawMessage              `json:"platform"`
		Environment []map[string]json.RawMessage `json:"environment"`
	}
	if err := json.Unmarshal(raw, &variants); err != nil {
		return err
	}
	for _, variant := range variants {
		if err := requireAuthoredPlatform(variant.Platform); err != nil {
			return err
		}
		for _, env := range variant.Environment {
			if raw, present := env["delivery"]; present {
				var delivery string
				if err := json.Unmarshal(raw, &delivery); err != nil || delivery == "" {
					return fmt.Errorf("environment delivery must be env or file when present")
				}
			}
		}
	}
	return nil
}
