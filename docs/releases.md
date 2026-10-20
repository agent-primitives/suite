# Versions and releases

These pages render **main**. They are development documentation, not a versioned
snapshot. Pin a tag when reproducing a build or reviewing a fixed contract.
See the [frozen legacy draft reader](legacy-draft.md) for the reviewed acceptance
baseline, its published v0.5.0 distribution and historical compatibility limits.

The first published module tag is
[v0.1.0](https://github.com/agent-primitives/suite/tree/v0.1.0).
Tags live at the repository root, not under an `agentsuite/` prefix.

## v0.6.0 — planned — portable loose-directory content identity

This is a **minor**, intentionally breaking loose-directory identity change.
Canonical content metadata no longer comes from host permission bits: regular
files default to non-executable `0644`, directories to `0755`/size zero, and
supported symbolic links to `0777`. Explicit ToolProvider payload inventories
supply their declared modes. A host `chmod +x` alone no longer changes identity
or grants executable content. Conflicting declared modes refuse.

Inventory decoding now rejects missing or null required `path`, `type`, `mode`,
`uid` and `gid` properties in both loose and archived inputs. Explicit zero mode
and root ownership remain valid. Direct `encoding/json.Unmarshal` of an
`InventoryEntry` also rejects unknown and duplicate properties. To repair malformed
authored inventories, declare the required values and rebind the variant digest,
provider descriptor and all ancestor descriptors; do not rewrite published artifacts.

Loose-directory semantic `ContentDigest` values and supplemental content-record
digests may change even when file bytes do not. Previously recorded loose
identities must be recomputed under an explicitly selected reader version. A
rebuild using these rules produces a newly packaged artifact where output bytes
change; update affected descriptors and obtain fresh evaluation/signing for that
new subject as required. Do not rewrite existing receipts to authorize it.

Published OCI artifacts continue to use their original tar modes and exact
inventory comparisons. Existing OCI/JCS digests, wire fields, schema bytes and
historical signatures/evidence are not relabelled, normalized or re-signed.
Archive and loose-directory comparisons may legitimately differ when an older
archive carries non-default modes not declared by the source manifests. Select
the original OCI artifact when reproducing or verifying that artifact's identity.

Unix host access checks remain separate from content modes. Windows loose
input uses handle-based owner/DACL checks, not synthesized POSIX permissions:
owner-only grants, a protected root, and no inherited broad grants. Unsupported
or unverifiable ACLs, filesystem security and reparse-backed entries refuse;
validation never repairs input ACLs. Windows CI exercises these refusal paths;
it is not Docker Desktop, kind or runtime qualification.

The [migration inventory](directory-identity.md) distinguishes every identified
suite/kmx loose-to-recorded comparison from unchanged byte/JCS/OCI/provenance
checks and records the required consumer packaging/cache follow-up. The
[frozen draft reader note](legacy-draft.md#v060-loose-directory-reader-exception)
records this explicit reader-version exception. This section describes unreleased
development; maintainers own release and schema-catalog preparation.

## [v0.5.0](https://github.com/agent-primitives/suite/releases/tag/v0.5.0) — 2026-10-19 — schema namespace and stricter validation

### Schema namespace

All 14 reference schema IDs move to `https://suite.agent-primitives.dev/schema/v0.5/`
plus the actual filename, including both `-v2` policy filenames. This is a minor
release identity migration, not a wire-format or validation-constraint change.
Select the whole release-local bundle and update editor/validator registries;
keep historical bundles separate, without global old-to-latest aliases. Schema
bytes differ only in `$id`; instance bytes, versions, media types and canonical
digests are unchanged by this migration. Canonical URLs must be verified after
the asset workflow, reviewed catalog update and site deployment. The validation
changes below have separate compatibility effects.

### Presence-sensitive validation

Validation now rejects Suite and ToolProvider extensions missing `critical`,
present empty or null ToolProvider `variants`, and explicitly null tool
`outputSchema` properties. These malformed documents could previously be accepted
after decoding erased property presence. Explicit `critical: false` remains valid;
the existing refusals of null `critical` and unknown `critical: true` extensions
are preserved. Agent extension acceptance is unchanged. Remote providers may omit
`variants` or combine remote metadata with nonempty bundled variants. Tools may
omit `outputSchema`; present objects still require valid file descriptors.

`ToolProvider` now implements `UnmarshalJSON` using the strict decoder, so plain
`encoding/json.Unmarshal` also rejects unknown or duplicate properties and other
malformed provider input previously accepted by that decoder.

This validation-acceptance change requires a **minor** Go module release under
the v0 policy. To migrate, explicitly declare extension criticality, omit absent
variants/output schemas instead of writing empty or null values, and rebind
changed documents and all ancestor descriptors. Public type shapes, schema IDs,
media types and canonical identity rules are unchanged. Validation remains offline.

### TypeScript policy identity

A [TypeScript policy package](https://github.com/agent-primitives/suite/tree/main/policy/typescript) is merged on main
for filesystem v1 and network-only v2 canonicalization, digests and payload
verification. Its source is included in v0.5.0; it remains a private, unpublished
ESM package, not an npm release. It does not implement administrative-policy composition or runtime
enforcement.

## [v0.4.0](https://github.com/agent-primitives/suite/releases/tag/v0.4.0) — 2026-10-16 — optional runtime profiles

Suites may bind runtime profiles and select multiple compositions for one
member/platform by explicit profile ID. New readers retain the legacy path;
omitting new fields preserves existing bytes, digests and report/diff output.
No migration or implicit fallback is performed. Older strict readers reject the
new fields. Use keyed Go literals for the extended public types.

`Suite`, `Composition` and `CompositionRef` now implement `UnmarshalJSON`, so
plain `encoding/json.Unmarshal` also uses strict decoding for these types,
rejecting unknown or duplicate properties and other malformed input previously
accepted by that decoder. Normatively valid legacy bytes remain compatible;
this tightens malformed-input acceptance, not the legacy wire contract.

Profile documents bind runtime/harness/renderer identities, an opaque consumer-owned
configuration ABI and an explicit image requirement. Validation checks declarations
and graph consistency, not runtime support. Evidence v1 is unchanged: two profiles
require separate passes against the same OCI manifest, with independent execution
expectations. No offline fixture establishes runtime execution or qualification.
Diff adds profile records and profile-aware composition keys with selective impact.

This format/API, validation and semantic-diff addition shipped in the **minor**
Go module release v0.4.0. Existing schema IDs, media types, spec version and
canonicalization remain unchanged; a new runtime-profile media type/schema is
added. Consumers using these additions must pin v0.4.0 or later before rollout.

## [v0.3.1](https://github.com/agent-primitives/suite/releases/tag/v0.3.1) — 2026-10-16 — OCI filesystem safety fix

The OCI loader refuses special files and symlinks in layout metadata and
referenced blobs before opening them, including FIFO inputs that previously
could hang offline validation or evidence verification. Blob directories must
also be real directories. Unix reads use nonblocking, no-follow opens; Windows
reads open reparse points rather than following them; layouts on specialized
Windows reparse-backed storage (for example cloud placeholders) may refuse and
should be materialized as ordinary local files. Other platforms retain
pre-open type and opened-file checks where native flags are unavailable.

This is a compatible fix for malformed filesystem envelopes: regular layouts,
public APIs, schema/media types, canonical bytes and descriptor digests are
unchanged. Previously followed layout-entry symlinks now refuse; materialize
regular files instead. Caller-selected root directory aliases and the content
layer's symlink semantics remain unchanged.

## [v0.3.0](https://github.com/agent-primitives/suite/releases/tag/v0.3.0) — 2026-10-16 — policies, Agent binding and inference contracts

v0.3.0 combines standalone network-only policy v2, optional per-Agent policy
descriptor binding with graph validation, and experimental inference and
execution contracts. v0.2.0 introduced the filesystem policy package.

- Opt into `agentsuite.policy/v2` / `SchemaVersionV2` for exact IPv4/TCP/port
  allowances. An empty list denies all; admin restrictions intersect.
- V1 remains supported. Administrative `denyWritePaths: null` now refuses
  instead of being treated as an omitted overlay; omission and `[]` remain
  valid. V1 path sets now explicitly use unsigned UTF-16 code-unit ordering,
  with a language-neutral vector. This can change canonical bytes and digests
  for affected non-BMP paths, so it shipped in the v0.3.0 minor release. The digest
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
  provider support. No runtime wiring or installed/active claim is included.

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
