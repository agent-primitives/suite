package agentsuite

import (
	"github.com/agent-primitives/suite/core"
	"github.com/agent-primitives/suite/oci"
)

// ValidatePath delegates to the shared oci implementation.
//
// Deprecated: use oci.ValidatePath.
func ValidatePath(value string) (*core.Report, error) { return oci.ValidatePath(value) }

// ValidateDirectory delegates to the shared oci implementation.
//
// Deprecated: use oci.ValidateDirectory.
func ValidateDirectory(root string) (*core.Report, error) { return oci.ValidateDirectory(root) }
