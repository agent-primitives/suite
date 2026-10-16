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
// Inspect report for conformance findings before using the content.
_ = report
```

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

[Go API reference](https://pkg.go.dev/github.com/agent-primitives/suite)
