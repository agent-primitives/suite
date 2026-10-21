// Package agentsuite validates the draft AgentSuite artifact format, including
// extracted directories, OCI layouts, evaluation evidence and semantic diffs.
//
// Portable types, JSON/identity helpers and value-level validation are defined
// in github.com/agent-primitives/suite/core. Their deprecated root exports are
// aliases and forwarders retained for one minor release before a separate
// pre-1.0 removal. Aliases preserve source type identity and methods, but
// reflection reports the new defining package.
//
// Packing, registry transfer, sandbox construction and runtime execution belong
// to consumers, not this library. Offline validation does not execute agents or
// authenticate evaluation claims.
package agentsuite
