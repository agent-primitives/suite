package artifact

import "github.com/agent-primitives/suite/core"

// ValidateImageReference checks a registry-qualified, sha256-digested image reference.
//
// Deprecated: use core.ValidateImageReference.
func ValidateImageReference(value string) error { return core.ValidateImageReference(value) }
