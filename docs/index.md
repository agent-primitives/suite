# AgentSuite

A portable, content-addressed definition of one or more related agents and the
exact ToolProviders used to construct their runnable sandboxes.

Suites carry a closed graph of agent, ToolProvider, composition and build-profile
manifests, distributed as OCI artifacts. Optional evaluation cases travel with
the agent definition; validation checks their storage and identity, not whether
they have passed.

## Start with the contract

- [Read the specification](../spec.md) for format and conformance requirements.
- [Download the schemas](schemas.md) for JSON Schema 2020-12 validation.
- [Use the Go package](go.md) for strict decoding, canonical identity and offline validation.
- [Explore the conformance fixtures](conformance.md) for concrete examples.

## Consumers

[kmx](https://kaimahi.dev/) uses AgentSuite for packaging and validation.
[agentsessions](https://github.com/agent-primitives/sessions) is a consumer
in the agent runtime ecosystem. An
[Orka](https://github.com/orka-agents/orka) dashboard integration is **planned**,
not a capability provided by this library.

[Source repository](https://github.com/agent-primitives/suite)

These docs follow **main**, which may include unreleased changes. For a fixed
contract, use the [v0.1.0 source tag](https://github.com/agent-primitives/suite/tree/v0.1.0)
and read the [versioning policy](releases.md).
