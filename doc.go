// Package agentsuite is the compatibility facade for AgentSuite's focused Go
// packages. Portable types and JSON/identity helpers live in core; directory/OCI
// validation and semantic diff in oci; evaluation claims in evidence; and
// explicitly selected stored-flow validation in experimental/flow.
//
// Root exports remain deprecated aliases and function forwarders for one minor
// release before a separate pre-1.0 removal. Aliases preserve source type
// identity and methods, but reflection reports the new defining packages.
//
// The artifact facades share an internal engine, keeping evidence and diff
// beside private validated graph state. Offline validation does not execute
// agents or authenticate evaluation claims. Packing and runtime enforcement
// belong to consumers, not this library.
package agentsuite
