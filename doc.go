// Package agentsuite documents AgentSuite's focused Go packages. The root
// package exports no API.
// Portable types and JSON/identity helpers live in core; directory/OCI validation
// and semantic diff in oci; evaluation claims and both verifiers in evidence;
// and explicitly selected stored-flow validation in experimental/flow.
// Standalone policy resolution lives in policy.
//
// The artifact facades share an internal engine, keeping evidence and diff
// beside private validated graph state. Offline validation does not execute
// agents or authenticate evaluation claims. Packing and runtime enforcement
// belong to consumers, not this library.
package agentsuite
