//go:build !unix && !windows

package agentsuite

// These platforms retain the portable pre-open type and opened-file checks.
const ociReadFlags = 0
