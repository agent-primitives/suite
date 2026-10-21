package agentsuite

import (
	"errors"
	"fmt"

	"github.com/agent-primitives/suite/core"
)

// RuntimeProfile is the portable core definition.
//
// Deprecated: use core.RuntimeProfile.
type RuntimeProfile = core.RuntimeProfile

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
