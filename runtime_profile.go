package agentsuite

import (
	"encoding/json"
	"errors"
	"fmt"
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
		if err := evidenceShape(fields[key], "implementation"); err != nil {
			return fmt.Errorf("runtime profile %s requires id, version and digest", key)
		}
	}
	profile := RuntimeProfile(value)
	if profile.SchemaVersion != SpecVersion || profile.MediaType != MediaTypeRuntimeProfile ||
		!identifierPattern.MatchString(profile.ID) || !evidenceToken(profile.ID) ||
		!identifierPattern.MatchString(profile.ConfigurationABI) ||
		!evidenceImplementation(profile.Runtime) || !evidenceImplementation(profile.Harness) || !evidenceImplementation(profile.Renderer) {
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
	if raw, present := fields["runtimeProfiles"]; present {
		if isJSONNull(raw) || len(value.RuntimeProfiles) == 0 {
			return errors.New("runtimeProfiles must be a nonempty array")
		}
		for _, ref := range value.RuntimeProfiles {
			if !identifierPattern.MatchString(ref.ID) || ref.Path == "" || ref.Descriptor.MediaType == "" ||
				!IsValidDigest(ref.Descriptor.Digest) || ref.Descriptor.Size < 0 {
				return errors.New("runtimeProfiles requires complete manifest references")
			}
		}
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
	if raw, present := fields["runtimeProfile"]; present {
		var id string
		if err := json.Unmarshal(raw, &id); err != nil || !identifierPattern.MatchString(id) {
			return errors.New("runtimeProfile must be a nonempty identifier")
		}
	}
	return nil
}

// Keep legacy tuple keys byte-for-byte when no runtime selector is present.
func compositionKey(agent string, platform Platform, profile string) string {
	key := agent + "@" + platform.String()
	if profile != "" {
		key += "@" + profile
	}
	return key
}

func (v *validator) loadRuntimeProfiles() error {
	var errs []error
	for _, ref := range v.suite.RuntimeProfiles {
		if _, exists := v.runtimes[ref.ID]; exists {
			errs = append(errs, fmt.Errorf("duplicate runtime profile %q", ref.ID))
			continue
		}
		data, err := v.content.data(ref.Path)
		if err != nil {
			errs = append(errs, fmt.Errorf("runtime profile %s: %w", ref.ID, err))
			continue
		}
		if ref.Descriptor.MediaType != MediaTypeRuntimeProfile || !matchesCanonicalDescriptor(data, ref.Descriptor) {
			errs = append(errs, fmt.Errorf("runtime profile %s digest mismatch", ref.ID))
			continue
		}
		var profile RuntimeProfile
		if err := Unmarshal(data, &profile); err != nil {
			errs = append(errs, fmt.Errorf("runtime profile %s: %w", ref.ID, err))
			continue
		}
		if profile.ID != ref.ID {
			errs = append(errs, fmt.Errorf("runtime profile reference %s points to %s", ref.ID, profile.ID))
			continue
		}
		v.runtimes[ref.ID] = profile
	}
	return errors.Join(errs...)
}
