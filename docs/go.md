# Go usage

Use Go 1.26.0 or newer. Pin a published module version:

```bash
go get github.com/agent-primitives/suite@v0.1.0
```

The module path ends in `suite`; the package name is `agentsuite`. Use an
explicit alias:

```go
import agentsuite "github.com/agent-primitives/suite"
```

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

## Standalone policy contracts

The `github.com/agent-primitives/suite/policy` package owns policy resolution,
canonical bytes and the policy-specific framed digest. `ValidatePath` validates
optional `Agent.Policy` FileRefs and reuses the same policy semantic decoder.
The root artifact content digest and policy-specific framed digest stay distinct.

The network-only v2 API is available from v0.3.0; pin that version or later
before using it. V1 filesystem policies remain supported without conversion.

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

[Go API reference](https://pkg.go.dev/github.com/agent-primitives/suite)
