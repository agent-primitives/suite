# Versions and releases

These pages render **main**. They are development documentation, not a versioned
snapshot. Pin a tag when reproducing a build or reviewing a fixed contract.

The first published module tag is
[v0.1.0](https://github.com/agent-primitives/suite/tree/v0.1.0).
Tags live at the repository root, not under an `agentsuite/` prefix.

## v0.3.0 — policies, Agent binding and inference contracts

v0.3.0 combines standalone network-only policy v2, optional per-Agent policy
descriptor binding with graph validation, and experimental inference and
execution contracts. v0.2.0 introduced the filesystem policy package.

- Opt into `agentsuite.policy/v2` / `SchemaVersionV2` for exact IPv4/TCP/port
  allowances. An empty list denies all; admin restrictions intersect.
- V1 remains supported. Administrative `denyWritePaths: null` now refuses
  instead of being treated as an omitted overlay; omission and `[]` remain
  valid. V1 path sets now explicitly use unsigned UTF-16 code-unit ordering,
  with a language-neutral vector. This can change canonical bytes and digests
  for affected non-BMP paths, so it ships in this next-minor change. The digest
  framing, schema identifier and existing artifact media type are unchanged.
  `SchemaVersion` deliberately continues to mean `agentsuite.policy/v1`.
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
- Agents gain optional `policy` FileRefs at `policies/<agent-id>.json`. Existing
  no-policy Agents remain valid and serialize unchanged; explicit null refuses.
  Use keyed `Agent` literals because the Go struct gains a field. Older validators
  that do not know this field must refuse rather than silently ignore it.
- Binding validates v1/v2 authored policy semantics, version-matched media types,
  exact ordinary content descriptors and closed policy graph membership in both
  extracted and OCI content. A changed policy requires rebinding its Agent and
  suite ancestors. Framed effective-policy identity is not an OCI descriptor hash.
- The top-level `policies/` namespace is now reserved and closed. Suites that
  previously stored unrelated or unreferenced files there must move them outside
  that namespace or bind valid owned policy files. An empty directory is allowed.
- The JSON codec moves unchanged to `internal/jsoncodec` behind the existing root
  public wrappers. Existing strict-decoding and canonical-byte behavior is retained.
- Neither standalone nor graph validation establishes runtime enforcement or
  provider support. No runtime wiring, installed/active claim or release publication
  is included.

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
