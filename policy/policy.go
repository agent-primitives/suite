package policy

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"path"
	"sort"
	"strings"
	"unicode/utf8"

	agentsuite "github.com/agent-primitives/suite"
)

// Match the root JSON decoder limit used by VerifyPayload.
const maxCanonicalBytes = 4 << 20

var digestDomain = []byte("agentsuite-effective-policy\x00v1\x00")

// DecodeSuitePolicy strictly decodes exactly one JSON object.
func DecodeSuitePolicy(data []byte) (SuitePolicy, error) {
	p, err := decodeSuiteWire(data)
	if err != nil {
		return p, fmt.Errorf("decode policy: %w", err)
	}
	if err := Validate(p); err != nil {
		return p, err
	}
	return p, nil
}

// DecodeAdministrativePolicy decodes the closed filesystem-only v1 administrative profile.
func DecodeAdministrativePolicy(data []byte) (AdministrativePolicy, error) {
	var wire struct {
		DenyWritePaths json.RawMessage `json:"denyWritePaths"`
	}
	if err := decodeStrict(data, &wire); err != nil {
		return AdministrativePolicy{}, fmt.Errorf("decode administrative policy: %w", err)
	}
	p := AdministrativePolicy{}
	if wire.DenyWritePaths != nil {
		if bytes.Equal(bytes.TrimSpace(wire.DenyWritePaths), []byte("null")) {
			return p, errors.New("denyWritePaths must not be null")
		}
		if err := json.Unmarshal(wire.DenyWritePaths, &p.DenyWritePaths); err != nil {
			return p, fmt.Errorf("denyWritePaths: %w", err)
		}
	}
	if len(p.DenyWritePaths) > 4096 {
		return p, errors.New("too many administrative denyWritePaths")
	}
	for _, item := range p.DenyWritePaths {
		if err := validatePath(item); err != nil {
			return p, fmt.Errorf("administrative: %w", err)
		}
	}
	return p, nil
}

func decodeStrict(data []byte, dst any) error {
	trimmed := bytes.TrimSpace(data)
	if len(trimmed) == 0 || trimmed[0] != '{' {
		return errors.New("policy JSON must be an object")
	}
	return agentsuite.Unmarshal(data, dst)
}

func Validate(p SuitePolicy) error {
	if p.Version == SchemaVersionV2 {
		return validateNetworkProfile(p.DenyWritePaths, p.Network, p.RequiredCapabilities)
	}
	if p.Version != SchemaVersion {
		return fmt.Errorf("unsupported policy version %q", p.Version)
	}
	if p.Network != nil {
		return errors.New("network is not allowed in v1 policy")
	}
	if len(p.DenyWritePaths) == 0 {
		return errors.New("denyWritePaths must not be empty")
	}
	if len(p.DenyWritePaths) > 4096 {
		return errors.New("too many denyWritePaths")
	}
	for _, item := range p.DenyWritePaths {
		if err := validatePath(item); err != nil {
			return err
		}
	}
	return validateCapabilities(p.RequiredCapabilities)
}

func validateCapabilities(capabilities []string) error {
	if len(capabilities) == 0 {
		return errors.New("requiredCapabilities must not be empty")
	}
	if len(capabilities) != 1 || capabilities[0] != FilesystemDenyWrite {
		return fmt.Errorf("requiredCapabilities must be exactly [%q]", FilesystemDenyWrite)
	}
	return nil
}

func validatePath(value string) error {
	if !utf8.ValidString(value) {
		return fmt.Errorf("path %q must be valid UTF-8", value)
	}
	if value == "" || !strings.HasPrefix(value, "/") || strings.ContainsRune(value, 0) || path.Clean(value) != value {
		return fmt.Errorf("path %q must be clean and absolute", value)
	}
	if value == "/" {
		return errors.New("root deny path is not supported")
	}
	return nil
}

func uniqueSorted(groups ...[]string) []string {
	values := make(map[string]struct{})
	for _, group := range groups {
		for _, value := range group {
			values[value] = struct{}{}
		}
	}
	out := make([]string, 0, len(values))
	for value := range values {
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}

// Resolve validates and monotonically composes requested and administrative restrictions.
func Resolve(s SuitePolicy, a AdministrativePolicy) (EffectivePolicy, error) {
	if err := Validate(s); err != nil {
		return EffectivePolicy{}, err
	}
	if s.Version == SchemaVersionV2 {
		return resolveNetwork(s, a)
	}
	if a.Network != nil {
		return EffectivePolicy{}, errors.New("administrative network is not allowed in v1 policy")
	}
	for _, item := range a.DenyWritePaths {
		if err := validatePath(item); err != nil {
			return EffectivePolicy{}, fmt.Errorf("administrative: %w", err)
		}
	}
	if len(a.DenyWritePaths) > 4096 {
		return EffectivePolicy{}, errors.New("too many administrative denyWritePaths")
	}
	paths := uniqueSorted(s.DenyWritePaths, a.DenyWritePaths)
	if len(paths) > 4096 {
		return EffectivePolicy{}, errors.New("too many effective denyWritePaths")
	}
	return EffectivePolicy{
		Version:              SchemaVersion,
		DenyWritePaths:       paths,
		RequiredCapabilities: []string{FilesystemDenyWrite},
	}, nil
}

// CanonicalBytes emits at most 4 MiB of deterministic UTF-8 JSON for a fully valid effective policy.
func CanonicalBytes(p EffectivePolicy) ([]byte, error) {
	if err := Validate(SuitePolicy(p)); err != nil {
		return nil, err
	}
	if p.Version == SchemaVersionV2 {
		p.Network = &NetworkPolicy{EgressAllow: normalizeEndpoints(p.Network.EgressAllow)}
	} else {
		p.DenyWritePaths = uniqueSorted(p.DenyWritePaths)
	}
	data, err := agentsuite.Marshal(p)
	if err != nil {
		return nil, err
	}
	if len(data) > maxCanonicalBytes {
		return nil, fmt.Errorf("effective policy exceeds %d bytes", maxCanonicalBytes)
	}
	return data, nil
}

// Digest returns a domain-separated, length-framed SHA-256 digest.
func Digest(data []byte) string {
	hash := sha256.New()
	hash.Write(digestDomain)
	var size [8]byte
	binary.BigEndian.PutUint64(size[:], uint64(len(data)))
	hash.Write(size[:])
	hash.Write(data)
	return "sha256:" + hex.EncodeToString(hash.Sum(nil))
}

func Payload(p EffectivePolicy) (ProviderPayload, error) {
	data, err := CanonicalBytes(p)
	if err != nil {
		return ProviderPayload{}, err
	}
	return ProviderPayload{
		Version:              p.Version,
		PolicyBytes:          data,
		PolicyDigest:         Digest(data),
		RequiredCapabilities: append([]string(nil), p.RequiredCapabilities...),
	}, nil
}

func VerifyPayload(p ProviderPayload) error {
	if p.Version != SchemaVersion && p.Version != SchemaVersionV2 {
		return errors.New("unsupported payload version")
	}
	if err := validateProfileCapabilities(p.RequiredCapabilities, p.Version); err != nil {
		return fmt.Errorf("payload: %w", err)
	}
	if Digest(p.PolicyBytes) != p.PolicyDigest {
		return errors.New("policy digest mismatch")
	}
	inner, err := DecodeSuitePolicy(p.PolicyBytes)
	if err != nil {
		return fmt.Errorf("decode effective policy: %w", err)
	}
	if inner.Version != p.Version {
		return errors.New("payload version does not match policy version")
	}
	effective := EffectivePolicy(inner)
	canonical, err := CanonicalBytes(effective)
	if err != nil {
		return err
	}
	if !bytes.Equal(canonical, p.PolicyBytes) {
		return errors.New("policy bytes are not canonical")
	}
	if !equalStrings(p.RequiredCapabilities, effective.RequiredCapabilities) {
		return errors.New("payload capabilities do not match policy capabilities")
	}
	return nil
}

func equalStrings(left, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for i := range left {
		if left[i] != right[i] {
			return false
		}
	}
	return true
}
