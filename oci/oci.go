// Package oci validates extracted directories and OCI layouts and computes semantic diffs.
//
// Types alias the shared internal implementation so graph, evidence and diff
// algorithms can retain their private validated state. Defining-package names
// in reflection refer to that implementation, and pkg.go.dev may show aliases
// rather than their fields. Portable manifest fields are documented in core.
package oci

import (
	"github.com/agent-primitives/suite/core"
	"github.com/agent-primitives/suite/internal/artifact"
)

// DiffAdded aliases the shared implementation; see the package documentation.
const DiffAdded = artifact.DiffAdded

// DiffModified aliases the shared implementation; see the package documentation.
const DiffModified = artifact.DiffModified

// DiffRemoved aliases the shared implementation; see the package documentation.
const DiffRemoved = artifact.DiffRemoved

// DiffReportSchemaVersion aliases the shared implementation; see the package documentation.
const DiffReportSchemaVersion = artifact.DiffReportSchemaVersion

// AffectedAgent aliases the shared implementation; see the package documentation.
type AffectedAgent = artifact.AffectedAgent

// DiffIdentity aliases the shared implementation; see the package documentation.
type DiffIdentity = artifact.DiffIdentity

// DiffLimitError aliases the shared implementation; see the package documentation.
type DiffLimitError = artifact.DiffLimitError

// DiffReport aliases the shared implementation; see the package documentation.
type DiffReport = artifact.DiffReport

// DiffSummary aliases the shared implementation; see the package documentation.
type DiffSummary = artifact.DiffSummary

// FieldChange aliases the shared implementation; see the package documentation.
type FieldChange = artifact.FieldChange

// RecordChange aliases the shared implementation; see the package documentation.
type RecordChange = artifact.RecordChange

// LayoutVersion identifies the OCI layout version used by suite artifacts.
const LayoutVersion = core.LayoutVersion

// MediaTypeArtifact identifies an AgentSuite OCI artifact.
const MediaTypeArtifact = core.MediaTypeArtifact

// MediaTypeEmptyConfig identifies the required OCI empty configuration.
const MediaTypeEmptyConfig = core.MediaTypeEmptyConfig

// MediaTypeContent identifies the compressed suite content layer.
const MediaTypeContent = core.MediaTypeContent

// ValidatePath delegates to the shared artifact implementation.
func ValidatePath(value string) (*core.Report, error) { return artifact.ValidatePath(value) }

// ValidateDirectory delegates to the shared artifact implementation.
func ValidateDirectory(root string) (*core.Report, error) { return artifact.ValidateDirectory(root) }

// DiffPaths delegates to the shared artifact implementation.
func DiffPaths(beforePath, afterPath string) (DiffReport, error) {
	return artifact.DiffPaths(beforePath, afterPath)
}
