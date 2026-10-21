package agentsuite

import "github.com/agent-primitives/suite/core"

// Marshal delegates to the shared core implementation.
//
// Deprecated: use core.Marshal.
func Marshal(value any) ([]byte, error) { return core.Marshal(value) }

// Unmarshal delegates to the shared core implementation.
//
// Deprecated: use core.Unmarshal.
func Unmarshal(data []byte, out any) error { return core.Unmarshal(data, out) }

// Digest delegates to the shared core implementation.
//
// Deprecated: use core.Digest.
func Digest(data []byte) (string, error) { return core.Digest(data) }

// DescriptorSizeAndDigestMatch delegates to the shared core implementation.
//
// Deprecated: use core.DescriptorSizeAndDigestMatch.
func DescriptorSizeAndDigestMatch(data []byte, descriptor Descriptor) bool {
	return core.DescriptorSizeAndDigestMatch(data, descriptor)
}

// MatchesCanonicalDescriptor delegates to the shared core implementation.
//
// Deprecated: use core.MatchesCanonicalDescriptor.
func MatchesCanonicalDescriptor(data []byte, descriptor Descriptor) bool {
	return core.MatchesCanonicalDescriptor(data, descriptor)
}

// IsValidDigest delegates to the shared core implementation.
//
// Deprecated: use core.IsValidDigest.
func IsValidDigest(value string) bool { return core.IsValidDigest(value) }
