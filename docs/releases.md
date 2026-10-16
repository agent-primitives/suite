# Versions and releases

These pages render **main**. They are development documentation, not a versioned
snapshot. Pin a tag when reproducing a build or reviewing a fixed contract.

The first published module tag is
[v0.1.0](https://github.com/agent-primitives/suite/tree/v0.1.0).
Tags live at the repository root, not under an `agentsuite/` prefix.

## Compatibility

Go module versions and format/schema versions are independent. A Go release does
not rename schema IDs or change wire identity implicitly.

While the Go module is v0, breaking API, validation-acceptance, wire-shape,
canonicalization/digest or semantic-diff changes require an explicitly documented
**minor release**. Compatible additions use a minor release; compatible fixes use
a patch release. Release notes should explain compatibility effects and migration.

Consumers pin published versions and verified module sums. Verify releases with
`GOWORK=off`; an outside-tree development workspace is not proof that a published
module can be fetched.

See the [contributor release policy](../CONTRIBUTING.md#release-policy) and
[repository tags](https://github.com/agent-primitives/suite/tags).
