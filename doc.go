// Package agentsuite is the compatibility facade for AgentSuite's focused Go
// packages. Portable types and JSON/identity helpers live in core; directory/OCI
// validation and semantic diff in oci; evaluation claims in evidence; and
// explicitly selected stored-flow validation in experimental/flow.
//
// Aliases preserve source type identity and methods, but reflection reports
// the new defining packages.
//
// The artifact facades share an internal engine, keeping evidence and diff
// beside private validated graph state. Offline validation does not execute
// agents or authenticate evaluation claims. Packing and runtime enforcement
// belong to consumers, not this library.
//
// Deprecated: use github.com/agent-primitives/suite/core,
// github.com/agent-primitives/suite/oci,
// github.com/agent-primitives/suite/evidence, or
// github.com/agent-primitives/suite/experimental/flow.
// Root aliases and forwarders are retained throughout v0.7.x and will be
// removed in v0.8.0.
package agentsuite
