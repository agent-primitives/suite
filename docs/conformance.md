# Conformance fixtures

The [testdata directory](../testdata/) contains canonical examples exercised by
the Go tests and the required **Go and conformance** CI job.

| Fixture | Coverage |
| --- | --- |
| [minimal](../testdata/minimal/) | An extracted suite, its agent, instructions, profile, composition and providers |
| [coordinator-workers](../testdata/coordinator-workers/) | Coordinator/worker relationships and packaged evaluation cases |
| [remote-mcp](../testdata/remote-mcp/) | Remote MCP declarations and catalog validation |
| [tool-providers](../testdata/tool-providers/) | CLI bundles and standalone provider compositions |

The tests also exercise OCI image-layout validation and semantic comparisons
between extracted content and OCI layouts. CI requires named conformance tests
to pass and rejects skipped tests.

## What a pass means

Validation establishes format and content-graph conformance. It does **not**
execute agents, assertions, tools or models; attest a sandbox; or prove runtime
conformance. See [specification §15](../spec.md#15-conformance) for the distinct
validator, sandbox-image and runtime responsibilities.

Run the fixtures with Go 1.26.0 or newer:

```bash
GOWORK=off go test -count=1 ./...
```
