package agentsuite

import "github.com/agent-primitives/suite/oci"

// DiffAdded is the oci definition.
//
// Deprecated: use oci.DiffAdded.
const DiffAdded = oci.DiffAdded

// DiffModified is the oci definition.
//
// Deprecated: use oci.DiffModified.
const DiffModified = oci.DiffModified

// DiffRemoved is the oci definition.
//
// Deprecated: use oci.DiffRemoved.
const DiffRemoved = oci.DiffRemoved

// DiffReportSchemaVersion is the oci definition.
//
// Deprecated: use oci.DiffReportSchemaVersion.
const DiffReportSchemaVersion = oci.DiffReportSchemaVersion

// AffectedAgent is the oci definition.
//
// Deprecated: use oci.AffectedAgent.
type AffectedAgent = oci.AffectedAgent

// DiffIdentity is the oci definition.
//
// Deprecated: use oci.DiffIdentity.
type DiffIdentity = oci.DiffIdentity

// DiffLimitError is the oci definition.
//
// Deprecated: use oci.DiffLimitError.
type DiffLimitError = oci.DiffLimitError

// DiffReport is the oci definition.
//
// Deprecated: use oci.DiffReport.
type DiffReport = oci.DiffReport

// DiffSummary is the oci definition.
//
// Deprecated: use oci.DiffSummary.
type DiffSummary = oci.DiffSummary

// FieldChange is the oci definition.
//
// Deprecated: use oci.FieldChange.
type FieldChange = oci.FieldChange

// RecordChange is the oci definition.
//
// Deprecated: use oci.RecordChange.
type RecordChange = oci.RecordChange

// DiffPaths delegates to the shared oci implementation.
//
// Deprecated: use oci.DiffPaths.
func DiffPaths(beforePath, afterPath string) (DiffReport, error) {
	return oci.DiffPaths(beforePath, afterPath)
}
