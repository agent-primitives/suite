# Versions and releases

These pages render **main**. They are development documentation, not a versioned
snapshot. Pin a tag when reproducing a build or reviewing a fixed contract.

The first published module tag is
[v0.1.0](https://github.com/agent-primitives/suite/tree/v0.1.0).
Tags live at the repository root, not under an `agentsuite/` prefix.

## Unreleased — standalone network-only policy v2 (next minor)

This development addition requires a new minor module release; no new tag is
created by the change. It is not included in v0.2.0, which introduced the
filesystem policy package.

- Opt into `agentsuite.policy/v2` / `SchemaVersionV2` for exact IPv4/TCP/port
  allowances. An empty list denies all; admin restrictions intersect.
- V1 remains supported. Administrative `denyWritePaths: null` now refuses
  instead of being treated as an omitted overlay; omission and `[]` remain
  valid. No v1 canonical bytes, digest framing, schema identifier or existing
  artifact media type is otherwise rewritten. `SchemaVersion` deliberately
  continues to mean `agentsuite.policy/v1`.
- Policy structs gain optional network fields. Use keyed Go composite literals;
  added fields can affect consumers that used unkeyed literals.
- Legacy administrative decoding remains v1-only. Select the policy version
  explicitly with `DecodeAdministrativePolicyForVersion` for v2. No automatic
  filesystem-to-network migration is performed; mixed-profile restrictions refuse.
- The existing policy digest domain identifies framing, not policy format version,
  and is reused unchanged. Consumers must support the new version/capability,
  preserve exact bytes, and reject mismatched payload versions/capabilities.
  `VerifyPayload` validates either contract, not provider support: a filesystem-only
  provider must still explicitly refuse v2/network requirements.
- Standalone validation is not runtime enforcement or Agent/OCI graph binding.
  Per-Agent descriptor binding is a subsequent change, not part of this release note.

See the [normative policy contract](../spec.md#appendix-b-standalone-policy-contracts-normative)
and [reference schemas](schemas.md).

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
