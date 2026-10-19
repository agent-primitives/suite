# Conformance fixtures

The [testdata directory](../testdata/) contains canonical examples exercised by
the Go tests and the required **Go and conformance** CI job.

| Fixture | Coverage |
| --- | --- |
| [minimal](../testdata/minimal/) | An extracted suite, its agent, instructions, profile, composition and providers |
| [policy-binding](../testdata/policy-binding/) | Optional Agent policy descriptor, canonical authored network policy and ancestor digest chain |
| [coordinator-workers](../testdata/coordinator-workers/) | Coordinator/worker relationships and packaged evaluation cases |
| [remote-mcp](../testdata/remote-mcp/) | Remote MCP declarations and catalog validation |
| [tool-providers](../testdata/tool-providers/) | CLI bundles and standalone provider compositions |

The tests also exercise OCI image-layout validation and semantic comparisons
between extracted content and OCI layouts. Policy binding tests cover both profiles,
absent-policy compatibility, closed policy namespaces, malformed/stale references,
semantic refusals and policy-to-suite identity propagation. An artifact policy
hash is ordinary content SHA-256; it is not the framed effective-policy digest.
CI requires named conformance tests
to pass and rejects skipped tests. Generated two-profile conformance tests extend
the minimal evaluation fixture without duplicating stored member/case files:
they check schema/decoder parity, profile selections and separate detached passes
against one exact OCI manifest. These are offline consistency tests, not execution
or cross-runtime qualification.

## What a pass means

Validation establishes format and content-graph conformance. It does **not**
execute agents, assertions, tools or models; attest a sandbox; or prove runtime
conformance. See [specification §7](../spec.md#15-conformance) for the distinct
validator, sandbox-image and runtime responsibilities.

Run the fixtures with Go 1.26.0 or newer:

```bash
GOWORK=off go test -count=1 ./...
```
