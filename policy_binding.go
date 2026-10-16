package agentsuite

import (
	"errors"
	"fmt"
	"strings"

	"github.com/agent-primitives/suite/policy"
)

func (v *validator) validatePolicies() error {
	files := map[string]bool{}
	var errs []error
	for id, agent := range v.agents {
		if agent.Policy == nil {
			continue
		}
		ref := *agent.Policy
		expectedPath := "policies/" + id + ".json"
		if ref.Path != expectedPath {
			errs = append(errs, fmt.Errorf("agent %s policy must be %s", id, expectedPath))
			continue
		}
		files[ref.Path] = true
		if err := v.validatePolicyDocument(ref); err != nil {
			errs = append(errs, fmt.Errorf("agent %s policy: %w", id, err))
		}
	}
	for name, entry := range v.content.entries {
		if name != "policies" && !strings.HasPrefix(name, "policies/") {
			continue
		}
		if name == "policies" && entry.Type == "directory" {
			continue
		}
		if entry.Type != "file" || !files[name] {
			errs = append(errs, fmt.Errorf("policy path %s is orphaned, unreferenced, or not a regular policy file", name))
		}
	}
	return errors.Join(errs...)
}

func (v *validator) validatePolicyDocument(ref FileRef) error {
	if !IsValidDigest(ref.Descriptor.Digest) {
		return errors.New("policy reference digest is invalid")
	}
	if ref.Descriptor.Size < 0 {
		return errors.New("policy reference size is invalid")
	}
	var expectedVersion string
	switch ref.Descriptor.MediaType {
	case MediaTypePolicyV1:
		expectedVersion = policy.SchemaVersion
	case MediaTypePolicyV2:
		expectedVersion = policy.SchemaVersionV2
	default:
		return errors.New("policy reference descriptor mediaType must be a supported policy media type")
	}
	data, err := v.content.data(ref.Path)
	if err != nil {
		return err
	}
	// Reject stale descriptors before strict decoding or canonicalization.
	if !descriptorSizeAndDigestMatch(data, ref.Descriptor) {
		return errors.New("policy document digest mismatch")
	}
	authored, err := policy.DecodeSuitePolicy(data)
	if err != nil {
		return err
	}
	if authored.Version != expectedVersion {
		return errors.New("policy version does not match descriptor mediaType")
	}
	// Bind authored JCS bytes, not normalized or administratively resolved
	// effective policy bytes (whose digest also uses a different domain).
	if !matchesCanonicalDescriptor(data, ref.Descriptor) {
		return errors.New("policy document must be stored as canonical JSON")
	}
	return nil
}
