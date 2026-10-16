# AgentSuite

AgentSuite is a portable, content-addressed definition of one or more related
agents and the exact ToolProviders used to construct their runnable sandboxes.
Suites are distributed as OCI artifacts and contain a closed graph of agent,
ToolProvider, composition, and build-profile manifests.

This standalone Go module, `github.com/agent-primitives/suite`, provides:

- public types for suites, agents, ToolProviders, callable Tools, compositions,
  and build profiles;
- media types and specification version constants;
- strict JSON decoding with closed-field and duplicate-key enforcement;
- JCS canonical encoding and digest calculation;
- offline validation of extracted content and OCI image-layout directories;
- optional [agent evaluations](spec.md#82-agent-evaluations) with ordered cases;
- closed JSON Schema 2020-12 documents in [schema/](schema/).

The normative format and conformance requirements are defined in
[spec.md](spec.md). Examples and conformance fixtures live in
[testdata/](testdata/).

## Go package

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
Licensed under the [Apache License 2.0](LICENSE).
See [SECURITY.md](SECURITY.md) for private vulnerability reporting and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for the Microsoft community policy.
