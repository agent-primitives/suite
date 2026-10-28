# Go usage

Use Go 1.26.0 or newer. Pin a published module version:

```bash
go get github.com/agent-primitives/suite@v0.7.0
```

The module path stays `github.com/agent-primitives/suite`. Import its focused
packages by responsibility, not the standalone root. These imports work with
the published v0.7.0 pin and with main, where root exports have been removed for
the unreleased breaking v0.8.0 minor.

<a id="portable-core-main-not-yet-released"></a>

## Focused packages (v0.7.0)

The `github.com/agent-primitives/suite/core` package owns portable manifests,
profiles, evaluation definitions, report/selection types and JSON/identity
helpers. It does not load directories or OCI layouts, verify evidence or execute
agents. The published pin above includes these packages. To work on main
locally instead, use the
[outside-tree workspace instructions](../CONTRIBUTING.md#local-development-across-repositories).

v0.7.0 also provides focused `oci`, `evidence` and `experimental/flow` packages.
Model, JSON and validation code can migrate without conversions:

```go
import (
    "github.com/agent-primitives/suite/core"
    "github.com/agent-primitives/suite/oci"
)

var suite core.Suite
if err := core.Unmarshal(data, &suite); err != nil {
    return err
}
report, err := oci.ValidateDirectory(directory)
```

v0.7.x retains deprecated root aliases and function forwarders as the one-minor
migration window. Main removes all 79 root type aliases, 35 constants and 15
forwarders for the unreleased breaking v0.8.0 minor, before module 1.0. The root
package is documentation-only; there is no replacement shim. v0.7.x patches must
come from the released minor line and keep the compatibility API.

Migrate before adopting v0.8.0. Type methods and JSON contracts stay unchanged,
but the v0.7.0 split changed defining-package reflection (including `%T` output).
Code relying on the old defining-package name must migrate separately.
Import by responsibility:

- `core`: portable types, strict JSON and content identity helpers.
- `oci`: `ValidateDirectory`, `ValidatePath`, `DiffPaths` and semantic-diff types.
- `evidence`: evidence types, `VerifyEvaluation` and the explicitly selected
  `VerifyEvaluationFlowV1Alpha1` verifier. Migrate `EvidenceImplementation` to
  canonical `core.EvidenceImplementation`, not an evidence-owned model.
- `experimental/flow`: stored v1alpha1 flow types, selectors and validation.
- `policy`: existing standalone policy resolution, unchanged.

The three facades share `internal/artifact`; the evidence/diff algorithms stay
beside the private graph inventory. Ordinary validation still compiles the
experimental validator: this boundary separates public APIs, not independent
feature engines. Their types alias that internal implementation, so reflection
shows its defining package and pkg.go.dev may show aliases rather than fields.
Portable manifest fields are documented in `core`. Keep existing exported
identifier spellings when migrating; no conversion or wire-format rewrite is
needed. The examples below use supported focused APIs with the published pin.

## Pure judge producer (main, not yet released)

Main additionally provides `github.com/agent-primitives/suite/judge`: a pure
request producer, original-response decoder and two-score verifier. It is not in
v0.7.0. Read the [producer profile and runtime trust boundary](judging.md) before
adopting a future containing release. Routes, credentials, content admission,
execution and retention remain runtime-owned; a pure pass is not qualification.

## Validate content offline

`ValidatePath` accepts an extracted content directory or an OCI image-layout
directory:

```go
report, err := oci.ValidatePath("./example-suite")
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

Use `oci.ValidateDirectory` for extracted content without OCI auto-detection.
Use `core.Unmarshal` rather than `encoding/json` directly when strict JSON decoding
is required, including duplicate-key and closed-field enforcement.

`core.Marshal` produces JCS-canonical JSON; `core.Digest` computes the corresponding
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

`evidence.VerifyEvaluation` retains evidence v1 and resolves the composition digest to
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
canonical bytes and the policy-specific framed digest. `oci.ValidatePath` validates
optional `Agent.Policy` FileRefs and reuses the same policy semantic decoder.
The root artifact content digest and policy-specific framed digest stay distinct.

The network-only v2 API was introduced in v0.3.0 and is included in v0.7.0
and later pins. V1 filesystem policies remain supported without conversion.

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

[Core API reference](https://pkg.go.dev/github.com/agent-primitives/suite/core) ·
[OCI API reference](https://pkg.go.dev/github.com/agent-primitives/suite/oci) ·
[Evidence API reference](https://pkg.go.dev/github.com/agent-primitives/suite/evidence) ·
[Experimental flow API reference](https://pkg.go.dev/github.com/agent-primitives/suite/experimental/flow)
