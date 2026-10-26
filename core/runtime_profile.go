package core

import (
	"encoding/json"
	"errors"
	"fmt"

	"github.com/agent-primitives/suite/internal/contract"
)

// RuntimeProfile pins execution requirements without overriding member content.
// ConfigurationABI is an opaque consumer-owned identifier, not a portable
// implementation catalog. Validation declares consistency, not runtime support.
type RuntimeProfile struct {
	SchemaVersion    string                 `json:"schemaVersion"`
	MediaType        string                 `json:"mediaType"`
	ID               string                 `json:"id"`
	Runtime          EvidenceImplementation `json:"runtime"`
	Harness          EvidenceImplementation `json:"harness"`
	Renderer         EvidenceImplementation `json:"renderer"`
	ConfigurationABI string                 `json:"configurationABI"`
	ImageRequired    bool                   `json:"imageRequired"`
}

func (p *RuntimeProfile) UnmarshalJSON(data []byte) error {
	type wire RuntimeProfile
	var value wire
	if err := Unmarshal(data, &value); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		return err
	}
	for _, key := range []string{"schemaVersion", "mediaType", "id", "runtime", "harness", "renderer", "configurationABI", "imageRequired"} {
		if raw, ok := fields[key]; !ok || isJSONNull(raw) {
			return fmt.Errorf("runtime profile requires non-null %s", key)
		}
	}
	for _, key := range []string{"runtime", "harness", "renderer"} {
		if _, code := contract.RequiredObject(fields[key], "id version digest"); code != "" {
			return fmt.Errorf("runtime profile %s requires id, version and digest", key)
		}
	}
	profile := RuntimeProfile(value)
	if profile.SchemaVersion != SpecVersion || profile.MediaType != MediaTypeRuntimeProfile ||
		!contract.IdentifierPattern.MatchString(profile.ID) || !contract.EvidenceToken(profile.ID) ||
		!contract.IdentifierPattern.MatchString(profile.ConfigurationABI) ||
		!validImplementation(profile.Runtime) || !validImplementation(profile.Harness) || !validImplementation(profile.Renderer) {
		return errors.New("invalid runtime profile identity or requirements")
	}
	*p = profile
	return nil
}

func (s *Suite) UnmarshalJSON(data []byte) error {
	type wire Suite
	var value wire
	if err := Unmarshal(data, &value); err != nil {
		return err
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		return err
	}
	if err := requireExtensionCritical(fields["extensions"]); err != nil {
		return err
	}
	if raw, present := fields["runtimeProfiles"]; present {
		if isJSONNull(raw) || len(value.RuntimeProfiles) == 0 {
			return errors.New("runtimeProfiles must be a nonempty array")
		}
		for _, ref := range value.RuntimeProfiles {
			if _, err := contract.ValidateContentPath(ref.Path); err != nil {
				return fmt.Errorf("runtime profile reference path: %w", err)
			}
			if !contract.IdentifierPattern.MatchString(ref.ID) || ref.Descriptor.MediaType == "" ||
				!IsValidDigest(ref.Descriptor.Digest) || ref.Descriptor.Size < 0 {
				return errors.New("runtimeProfiles requires complete manifest references")
			}
		}
	}
	if err := requireNonNullFields(fields); err != nil {
		return err
	}
	*s = Suite(value)
	return nil
}

func (c *Composition) UnmarshalJSON(data []byte) error {
	type wire Composition
	var value wire
	if err := Unmarshal(data, &value); err != nil {
		return err
	}
	if err := runtimeSelector(data); err != nil {
		return err
	}
	if value.ToolProviders == nil {
		return errors.New("toolProviders must be present and non-null")
	}
	*c = Composition(value)
	return nil
}

func (c *CompositionRef) UnmarshalJSON(data []byte) error {
	type wire CompositionRef
	var value wire
	if err := Unmarshal(data, &value); err != nil {
		return err
	}
	if err := runtimeSelector(data); err != nil {
		return err
	}
	*c = CompositionRef(value)
	return nil
}

func runtimeSelector(data []byte) error {
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(data, &fields); err != nil {
		return err
	}
	if err := requireAuthoredPlatform(fields["platform"]); err != nil {
		return err
	}
	if raw, present := fields["runtimeProfile"]; present {
		var id string
		if err := json.Unmarshal(raw, &id); err != nil || !contract.IdentifierPattern.MatchString(id) {
			return errors.New("runtimeProfile must be a nonempty identifier")
		}
	}
	return nil
}

func validImplementation(v EvidenceImplementation) bool {
	return contract.EvidenceImplementation(v.ID, v.Version, v.Digest)
}
