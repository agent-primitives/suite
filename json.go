package agentsuite

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"

	"github.com/agent-primitives/suite/internal/jsoncodec"
	"github.com/gowebpki/jcs"
)

const (
	maxJSONBytes         = jsoncodec.MaxBytes
	maxJSONDepth         = jsoncodec.MaxDepth
	maxJSONObjectMembers = jsoncodec.MaxObjectMembers
)

var (
	errJSONMemberLimit = jsoncodec.ErrMemberLimit
	errJSONDepthLimit  = jsoncodec.ErrDepthLimit
)

// Marshal serializes value as JSON Canonicalization Scheme (JCS) JSON.
func Marshal(value any) ([]byte, error) { return jsoncodec.Marshal(value) }

// Unmarshal decodes one strict AgentSuite JSON document.
//
// It rejects duplicate or unknown fields, invalid UTF-8, lossy JCS number
// representations, trailing values, and documents exceeding the format's
// declared implementation limits.
func Unmarshal(data []byte, out any) error { return jsoncodec.Unmarshal(data, out) }

func decodeStrict(data []byte, out any) error { return Unmarshal(data, out) }

func decodeJSONValue(data []byte) (any, error) { return jsoncodec.DecodeValue(data) }

func sameExactJSONValue(a, b any) bool { return jsoncodec.SameExactValue(a, b) }

// Digest returns the SHA-256 digest of the JCS representation of data.
func Digest(data []byte) (string, error) {
	canonical, err := jcs.Transform(data)
	if err != nil {
		return "", fmt.Errorf("canonicalize JSON: %w", err)
	}
	sum := sha256.Sum256(canonical)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

func canonicalDigest(data []byte) (string, error) {
	return Digest(data)
}

// canonicalSize returns the byte length of the JCS-canonical representation
// of data, describing the same canonical bytes as canonicalDigest.
func canonicalSize(data []byte) (int64, error) {
	canonical, err := jcs.Transform(data)
	if err != nil {
		return 0, fmt.Errorf("canonicalize JSON: %w", err)
	}
	return int64(len(canonical)), nil
}

// descriptorSizeAndDigestMatch performs the cheap length and raw-byte digest
// comparison against descriptor, without canonicalizing data at all. It lets
// a caller reject a size/digest-mismatched document before investing in full
// JSON parsing (strict decoding, canonicalization, or reflection-based field
// checks). It does not confirm that data is itself stored in canonical form;
// callers that parse data after this check still need
// MatchesCanonicalDescriptor to enforce that invariant.
func descriptorSizeAndDigestMatch(data []byte, descriptor Descriptor) bool {
	return DescriptorSizeAndDigestMatch(data, descriptor)
}

// DescriptorSizeAndDigestMatch performs the cheap length and raw-byte digest
// comparison against descriptor, without canonicalizing data at all. It lets
// a caller reject a size/digest-mismatched document before investing in full
// JSON parsing (strict decoding, canonicalization, or reflection-based field
// checks). It does not confirm that data is itself stored in canonical form;
// callers that parse data after this check still need
// MatchesCanonicalDescriptor to enforce that invariant.
func DescriptorSizeAndDigestMatch(data []byte, descriptor Descriptor) bool {
	return int64(len(data)) == descriptor.Size && digestBytes(data) == descriptor.Digest
}

// matchesCanonicalDescriptor reports whether data is itself stored as its
// own RFC 8785 JCS canonical bytes, and whether descriptor's digest and size
// describe that same canonical representation. A descriptor binding
// canonical identity is satisfied only when the stored bytes are already
// canonical: differently formatted (for example pretty-printed) but
// semantically equivalent JSON is rejected, since a consumer must be able to
// load the referenced bytes directly without re-canonicalizing them first.
func matchesCanonicalDescriptor(data []byte, descriptor Descriptor) bool {
	return MatchesCanonicalDescriptor(data, descriptor)
}

// MatchesCanonicalDescriptor reports whether data is itself stored as its
// own RFC 8785 JCS canonical bytes, and whether descriptor's digest and size
// describe that same canonical representation. A descriptor binding
// canonical identity is satisfied only when the stored bytes are already
// canonical: differently formatted (for example pretty-printed) but
// semantically equivalent JSON is rejected, since a consumer must be able to
// load the referenced bytes directly without re-canonicalizing them first.
// Callers outside this package (for example builders that re-read pinned
// child manifests) should use this instead of re-deriving digest/size checks
// by hand, so every consumer enforces the same stored-byte identity rule.
func MatchesCanonicalDescriptor(data []byte, descriptor Descriptor) bool {
	// Reject on raw length and raw-byte digest first: cheap checks that avoid
	// canonicalizing data at all when it plainly cannot match. If data is
	// itself already canonical (the required storage form), its raw SHA-256
	// digest equals the canonical digest, so this is not merely a shortcut
	// for the common case, it rules out any non-canonically stored document
	// too, since such a document's raw bytes cannot hash to the canonical
	// digest of a differently formatted equivalent.
	if int64(len(data)) != descriptor.Size || digestBytes(data) != descriptor.Digest {
		return false
	}
	canonical, err := jcs.Transform(data)
	return err == nil && bytes.Equal(data, canonical)
}

func digestBytes(data []byte) string {
	sum := sha256.Sum256(data)
	return "sha256:" + hex.EncodeToString(sum[:])
}

// IsValidDigest reports whether value is a canonical AgentSuite SHA-256 digest.
func IsValidDigest(value string) bool {
	if !strings.HasPrefix(value, "sha256:") || len(value) != len("sha256:")+64 {
		return false
	}
	for _, r := range value[len("sha256:"):] {
		if r < '0' || r > '9' && r < 'a' || r > 'f' {
			return false
		}
	}
	return true
}
