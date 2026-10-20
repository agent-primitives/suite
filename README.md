# AgentSuite

AgentSuite is a portable, content-addressed definition of one or more related
agents and the exact ToolProviders used to construct their runnable sandboxes.
Suites are distributed as OCI artifacts and contain a closed graph of agent,
ToolProvider, composition, and build-profile manifests.

## Why AgentSuite?

OCI supplies the distribution format; AgentSuite adds the agent-definition
contract: instructions, exact ToolProviders, compositions, canonical identity
and optional evaluation requirements. The aim is to let producers and consumers
exchange one defined content graph rather than inventing those bindings for
each integration. Portability here is of definitions, not demonstrated equivalent
execution across runtimes.

## Status and implementations

The [specification](spec.md) is a draft. The module is pre-1.0; see the
[compatibility and release policy](CONTRIBUTING.md#release-policy) before adopting
or changing the contract. The [stability boundaries](spec.md#111-stability-boundaries-and-compatibility)
define the intended wire-1.0 stable core, not a released stable format.
[Capability-based inference, build-profile execution and the AgentKit configuration mapping](docs/schemas.md#experimental-execution-and-inference-contracts)
remain experimental; validation does not establish runtime support.

- [kmx](https://kaimahi.dev/) uses AgentSuite for
  [packaging and validation](https://github.com/kaimahi-agents/kaimahi/tree/1617117e6b73fc00403ba59e6edecbe05fa58dc1/internal/kmx/agentsuite/oras);
  [Kaimahi's go.mod](https://github.com/kaimahi-agents/kaimahi/blob/1617117e6b73fc00403ba59e6edecbe05fa58dc1/go.mod)
  pins this module at v0.4.0.
- [agentsessions](https://github.com/agent-primitives/sessions) is related runtime
  ecosystem work, not a direct AgentSuite implementation.
- The [documentation site](https://suite.agent-primitives.dev/) lists an
  [Orka](https://github.com/orka-agents/orka) dashboard integration as planned,
  not provided by this library.

The [documentation site](https://suite.agent-primitives.dev/) tracks main and
may include unreleased changes.

## Go package

This standalone Go module, `github.com/agent-primitives/suite`, provides:

- public types for suites, agents, ToolProviders, callable Tools, compositions,
  build profiles, and optional [runtime profiles](spec.md#111-runtime-profiles);
- media types and specification version constants;
- strict JSON decoding with closed-field and duplicate-key enforcement;
- JCS canonical encoding and digest calculation;
- offline validation of extracted content and OCI image-layout directories;
- optional [agent evaluations](spec.md#82-agent-evaluations) with ordered cases;
- closed JSON Schema 2020-12 documents in [schema/](schema/).

The normative format and conformance requirements are defined in
[spec.md](spec.md). Examples and conformance fixtures live in
[testdata/](testdata/).

Use Go 1.26.0 or newer. The module path ends in `suite`, but the Go package
remains `agentsuite`; use an explicit import alias:

```go
import agentsuite "github.com/agent-primitives/suite"

data, err := agentsuite.Marshal(suite)
if err != nil {
    return err
}

digest, err := agentsuite.Digest(data)
```

`Unmarshal` should be used for AgentSuite JSON rather than `encoding/json`
directly when strict format enforcement is required.

`ValidatePath` validates either an extracted AgentSuite content directory or
an OCI image-layout directory and returns a conformance report. Consumers that
read loose manifests should use `ValidateDirectory` to validate extracted
content explicitly, without OCI layout auto-detection.

The Go validator compiles evaluation regex assertions with `regexp`, whose
accepted expression syntax is RE2. Validation does not execute evaluations,
tools, models or agents, and does not attest runtime or sandbox conformance.

Builders, packers, registry transfer, sandbox-image construction, and
builder-owned image metadata are implementation concerns and are not part of
this package. Kaimahi's builder-owned
[sandbox-binding schema](https://github.com/kaimahi-agents/kaimahi/blob/e48f063f422bd38b7f92173351defd21bfcda5cc/internal/kmx/agentsuite/schema/sandbox-binding.schema.json)
remains in its source repository.

## Development and releases

See [CONTRIBUTING.md](CONTRIBUTING.md) for verification, cross-repository
`go.work` development and [release policy](CONTRIBUTING.md#release-policy).
Releases are root tags (`vX.Y.Z`) cut by the maintainers.

Repository extraction does not change schema IDs, media types, format versions,
canonical bytes or digests. Go module versions and format versions are independent.

## Project policies and provenance

Extracted with portable history from
[kaimahi-agents/kaimahi](https://github.com/kaimahi-agents/kaimahi/tree/e48f063f422bd38b7f92173351defd21bfcda5cc/agentsuite).
Licensed under the [MIT License](LICENSE). Copyright (c) Microsoft Corporation.
See [SECURITY.md](SECURITY.md) for private vulnerability reporting and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for the Microsoft community policy.
