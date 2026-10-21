# Go usage

Use Go 1.26.0 or newer. Pin a published module version:

```bash
go get github.com/agent-primitives/suite@v0.4.0
```

The module path ends in `suite`; the package name is `agentsuite`. Use an
explicit alias:

```go
import agentsuite "github.com/agent-primitives/suite"
```

## Portable core (main, not yet released)

The `github.com/agent-primitives/suite/core` package owns portable manifests,
profiles, evaluation definitions, report/selection types and JSON/identity
helpers. It does not load directories or OCI layouts, verify evidence or execute
agents. The published pin above predates this package; keep using the root
import with that release. To work on main locally, use the
[outside-tree workspace instructions](../CONTRIBUTING.md#local-development-across-repositories).

After a release containing `core`, model and JSON code can migrate without
conversions:

```go
import (
    agentsuite "github.com/agent-primitives/suite"
    "github.com/agent-primitives/suite/core"
)

var suite core.Suite
if err := core.Unmarshal(data, &suite); err != nil {
    return err
}
report, err := agentsuite.ValidateDirectory(directory)
```

Moved root types remain true aliases and moved functions remain forwarders.
Their deprecated root exports are retained for one minor release; their later
removal requires a separate pre-1.0 minor. Type methods and JSON contracts stay
unchanged, but reflection reports the new defining package (including `%T`
output). Code relying on the old defining-package name must migrate separately.
The root still owns graph/OCI validation, evidence, semantic diff and explicitly
selected experimental flow APIs in this stage. The existing `policy` import is
unchanged.

## Validate content offline

`ValidatePath` accepts an extracted content directory or an OCI image-layout
directory:

```go
report, err := agentsuite.ValidatePath("./example-suite")
if err != nil {
    return err
}
```

A non-nil error means validation failed. On success, `report` summarizes the
validated suite's name, counts, capabilities and composition selections; it does
not contain a separate list of conformance failures.

OCI metadata and referenced blobs must be regular files. FIFOs, devices,
sockets and symlinks refuse before opening; blob directories must not be
symlinks. These rules also apply to the OCI reads used by `VerifyEvaluation`.
The content layer's own symlink inventory rules are separate and unchanged.

Use `ValidateDirectory` for extracted content without OCI auto-detection.
Use `Unmarshal` rather than `encoding/json` directly when strict JSON decoding
is required, including duplicate-key and closed-field enforcement.

`Marshal` produces JCS-canonical JSON; `Digest` computes the corresponding
content digest. Canonicalization, descriptors and the closed graph are defined
by the [specification](../spec.md).

Evaluation regex syntax is RE2 as implemented by Go's `regexp` package.
Validation does not execute evaluations or establish a passing result.
Builders, registry transfer and runtime execution belong to consumers, not this
package.

## Optional runtime profiles

`Suite.RuntimeProfiles` references digest-bound `RuntimeProfile` documents.
`CompositionRef.RuntimeProfile` and `Composition.RuntimeProfile` must agree.
Select the exact member/platform/profile tuple, not the first composition.
Reports preserve both selections while deduplicating `AgentPlatforms`.
`DiffPaths` emits `runtimeProfile` records and profile-aware composition IDs.

`VerifyEvaluation` retains evidence v1 and resolves the composition digest to
its profile before checking runtime/harness/renderer and profile identities.
Two profiles need two detached passes against the exact same OCI manifest;
passing one never qualifies the other. Expectations must be independently resolved.
Image identity belongs in the caller/producer non-secret execution configuration
digest; this offline verifier cannot inspect its preimage or execute a runtime.
Runtime and configuration ABI support are consumer-owned, not library catalogs.

Use keyed literals for the extended public structs. Omitted fields retain legacy
serialization and identity. Runtime profiles were released in v0.4.0. Older
strict readers reject profiled suites; consumers using them must pin v0.4.0 or
later. See
[runtime profiles](../spec.md#111-runtime-profiles) and [compatibility](releases.md#compatibility).

## Standalone policy contracts

The `github.com/agent-primitives/suite/policy` package owns policy resolution,
canonical bytes and the policy-specific framed digest. `ValidatePath` validates
optional `Agent.Policy` FileRefs and reuses the same policy semantic decoder.
The root artifact content digest and policy-specific framed digest stay distinct.

The network-only v2 API was introduced in v0.3.0 and is included in the v0.4.0
pin above. V1 filesystem policies remain supported without conversion.

Use `DecodeSuitePolicy` to read the explicit version, then
`DecodeAdministrativePolicyForVersion(data, suite.Version)`, `Resolve` and
`Payload`. Verify a provider carrier with `VerifyPayload`, and preserve its
`PolicyBytes` unchanged. Legacy `DecodeAdministrativePolicy` stays v1-only.
This flow resolves effective deployment policy separately from optional authored
Agent bindings. Graph validation verifies the declared authored file's bytes;
it does not apply administrative restrictions or execute/qualify a runtime.

The optional `Agent.Policy` points to `policies/<agent-id>.json` using
`MediaTypePolicyV1` or `MediaTypePolicyV2`, matching the document's version.
Its descriptor hashes the exact authored JCS bytes with ordinary content SHA-256;
never put `policy.Digest` in that descriptor. Bind the policy descriptor into the
Agent, then rebind the Agent descriptor into the suite manifest. Existing Agents
with nil `Policy` retain their prior serialized form. Use keyed struct literals.

See the
[normative specification](../spec.md#appendix-b-standalone-policy-contracts-normative).

## Format and package scope

AgentSuite defines one or more related agents and the exact ToolProviders used
to construct their runnable sandboxes. Suites are distributed as Open Container
Initiative (OCI) artifacts and contain a closed graph of agent, ToolProvider,
composition and build-profile manifests. The format adds instructions, exact tool
provider bindings, compositions, canonical identity and optional evaluation
requirements to OCI distribution. Portability is of definitions, not demonstrated
equivalent execution across runtimes.

This standalone Go module, `github.com/agent-primitives/suite`, provides:

- public types for suites, agents, ToolProviders, callable Tools, compositions,
  build profiles and optional [runtime profiles](../spec.md#111-runtime-profiles);
- media types and specification version constants;
- strict JSON decoding with closed-field and duplicate-key enforcement;
- JSON Canonicalization Scheme (JCS) encoding and digest calculation;
- offline validation of extracted content and OCI image-layout directories;
- optional [agent evaluations](../spec.md#82-agent-evaluations) with ordered cases;
- closed JSON Schema 2020-12 documents in [schema/](../schema/).

The normative format and conformance requirements are defined in
[spec.md](../spec.md). Examples and conformance fixtures live in
[testdata/](../testdata/). Validation does not execute evaluations, tools, models
or agents, and does not attest runtime or sandbox conformance.

The specification is a draft. Its
[stability boundaries](../spec.md#111-stability-boundaries-and-compatibility)
define the intended wire-1.0 stable core, not a released stable format.
[Capability-based inference, build-profile execution and the AgentKit configuration mapping](schemas.md#experimental-execution-and-inference-contracts)
remain experimental; validation does not establish runtime support.

Builders, packers, registry transfer, sandbox-image construction and
builder-owned image metadata are consumer responsibilities. Kaimahi's
[sandbox-binding schema](https://github.com/kaimahi-agents/kaimahi/blob/e48f063f422bd38b7f92173351defd21bfcda5cc/internal/kmx/agentsuite/schema/sandbox-binding.schema.json)
remains in its source repository.

Go module versions and format versions are independent. Repository extraction
did not change schema IDs, media types, format versions, canonical bytes or
digests; later changes follow the [release policy](../CONTRIBUTING.md#release-policy).

## Integrations and provenance

- [kmx](https://kaimahi.dev/) uses AgentSuite for
  [packaging and validation](https://github.com/kaimahi-agents/kaimahi/tree/1617117e6b73fc00403ba59e6edecbe05fa58dc1/internal/kmx/agentsuite/oras).
  Its [go.mod at that recorded commit](https://github.com/kaimahi-agents/kaimahi/blob/1617117e6b73fc00403ba59e6edecbe05fa58dc1/go.mod)
  pins this module at v0.4.0; that source link is not a claim about its current pin.
- [Sessions](https://github.com/agent-primitives/sessions) is related runtime
  ecosystem work, not a direct AgentSuite implementation.
- The [documentation site](https://suite.agent-primitives.dev/) lists an
  [Orka](https://github.com/orka-agents/orka) dashboard integration as planned,
  not provided by this library. The site tracks main and may include unreleased changes.

Extracted with portable history from
[kaimahi-agents/kaimahi](https://github.com/kaimahi-agents/kaimahi/tree/e48f063f422bd38b7f92173351defd21bfcda5cc/agentsuite).
See [contributing](../CONTRIBUTING.md) for local cross-repository development and
maintainer-owned root release tags.

[Root API reference](https://pkg.go.dev/github.com/agent-primitives/suite) ·
[Core API reference](https://pkg.go.dev/github.com/agent-primitives/suite/core)
(available after a release containing `core`)
