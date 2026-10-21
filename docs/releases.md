# Versions and releases

These pages render **main**. They are development documentation, not a versioned
snapshot. Pin a tag when reproducing a build or reviewing a fixed contract.
See the [frozen legacy draft reader](legacy-draft.md) for the reviewed acceptance
baseline, its published v0.5.0 distribution and historical compatibility limits.

The first published module tag is
[v0.1.0](https://github.com/agent-primitives/suite/tree/v0.1.0).
Tags live at the repository root, not under an `agentsuite/` prefix.

## [v0.7.0](https://github.com/agent-primitives/suite/releases/tag/v0.7.0) — 2026-10-21 — focused Go packages

### Summary
- **Focused imports:** portable `core`, directory/OCI/diff `oci`, evaluation `evidence` and explicitly selected `experimental/flow`; existing `policy` is unchanged.
- **Root compatibility through v0.7.x:** migrate before the planned breaking removal in v0.8.0, before module 1.0.
- **Fresh `/schema/v0.7/` IDs:** validation constraints, wire/JSON contracts, canonical artifact identities and dependencies are unchanged.

### What moved

The standalone Go module remains `github.com/agent-primitives/suite`, with one root module tag `v0.7.0`. PRs [#47](https://github.com/agent-primitives/suite/pull/47) and [#48](https://github.com/agent-primitives/suite/pull/48) split its root package into focused public imports:

| Import | Responsibility / examples |
| --- | --- |
| `github.com/agent-primitives/suite/core` | Portable manifests, profiles, evaluation definitions and reports; strict `Marshal`/`Unmarshal`, digest/descriptor helpers and value validation such as `ValidateExecutionContract` and `ValidateImageReference`. |
| `github.com/agent-primitives/suite/oci` | `ValidatePath`, `ValidateDirectory`, `DiffPaths` and semantic-diff types. |
| `github.com/agent-primitives/suite/evidence` | Evaluation claim types, `VerifyEvaluation` and the explicitly selected `VerifyEvaluationFlowV1Alpha1`. |
| `github.com/agent-primitives/suite/experimental/flow` | Stored `FlowV1Alpha1` types/selectors, `FlowV1Alpha1Graph`, `ValidatePathFlowV1Alpha1` and `ValidateDirectoryFlowV1Alpha1`. |
| `github.com/agent-primitives/suite/policy` | Existing standalone policy APIs; import path unchanged. |

The three artifact-facing facades share `internal/artifact`, keeping loaders, evidence/diff algorithms and private validated graph state together without new graph accessors. Consumers must not import the internal engine. `core` does not load directories/OCI layouts, verify claims or execute agents. Ordinary artifact validation still compiles the experimental validator in the shared engine; this is a public API split, not independent feature engines.

### Compatibility window: v0.7.x, then removal in v0.8.0

All existing root imports (`agentsuite "github.com/agent-primitives/suite"`) remain supported throughout **v0.7.x** through deprecated true type aliases, constant aliases and real function forwarders. There are 79 root type aliases, 35 constants and 15 function forwarders in the checked source. No root-export removal belongs in a v0.7 patch.

**Migrate during v0.7.x. The planned removal is v0.8.0**, a separately reviewed breaking minor release before module 1.0. This is one minor-version compatibility window, not an extra minor after v0.7.x. The removal is tracked from the [1.0 checklist #30](https://github.com/agent-primitives/suite/issues/30), following [#45](https://github.com/agent-primitives/suite/issues/45).

Within v0.7, aliases preserve assignability between root and focused imports, methods, JSON behavior and `errors.As` identity. **Defining-package reflection names are not preserved**: `reflect.Type.PkgPath` and `%T` can now name `core` or the internal implementation rather than the former root package. Audit code that keys registries or persists reflection/type-name strings; do not use those names as wire identifiers. The artifact facades' pkg.go.dev pages may display aliases rather than their fields; portable manifest fields are documented in `core`.

### Consumer migration

Update the single module pin, then migrate imports by responsibility:

```sh
go get github.com/agent-primitives/suite@v0.7.0
GOWORK=off go test ./...
```

Do not use separate `core/v0.7.0` or `oci/v0.7.0` tags. Keep existing exported identifier spellings; no model conversions or artifact rewrites are needed.

| Former root use | Focused use |
| --- | --- |
| `agentsuite.Suite`, `agentsuite.RuntimeProfile`, `agentsuite.Report` | `core.Suite`, `core.RuntimeProfile`, `core.Report` |
| `agentsuite.Marshal`, `Unmarshal`, `Digest`, descriptor helpers | Corresponding `core` functions |
| `agentsuite.ValidateExecutionContract`, `ValidateImageReference` | Corresponding `core` functions |
| `agentsuite.EvidenceImplementation` | `core.EvidenceImplementation` (the canonical portable identity) |
| `agentsuite.ValidatePath`, `ValidateDirectory`, `DiffPaths` | Corresponding `oci` functions; diff types also live in `oci` |
| `agentsuite.ExpectedEvaluation`, `EvidenceRefusal`, `VerifyEvaluation` | Corresponding `evidence` types/functions |
| `agentsuite.VerifyEvaluationFlowV1Alpha1` | `evidence.VerifyEvaluationFlowV1Alpha1`, not the flow package |
| Root `FlowV1Alpha1` types/selectors and the two explicit flow validators | Same names from `experimental/flow` (usually imported as `flow`) |

For example, model/JSON code and directory/OCI validation no longer need the root package:

```go
import (
    "github.com/agent-primitives/suite/core"
    "github.com/agent-primitives/suite/oci"
)

var suite core.Suite
if err := core.Unmarshal(data, &suite); err != nil {
    return err
}
report, err := oci.ValidatePath(path)
```

Pin published versions and verify in a clean checkout with `GOWORK=off`; a local workspace is only a rehearsal, not proof the new tag can be fetched. The older Sessions example import `github.com/kaimahi-agents/kaimahi/agentsuite` is a different legacy path and is not automatically migrated by these aliases.

### Behavior, schema and stability boundaries

The package moves do not change validation acceptance, security policy, evidence refusal ordering, semantic diff behavior, wire/JSON shapes, media types or canonical content/OCI digest rules. Existing artifact bytes, descriptors, signatures and evidence must not be rewritten for an import migration. Go module dependencies and the Go 1.26.0 minimum are unchanged from v0.6.0.

The split PRs left schema, fixture and published catalog bytes untouched. Separately, [#49](https://github.com/agent-primitives/suite/pull/49) froze all 15 reference schemas under `https://suite.agent-primitives.dev/schema/v0.7/` for this release, changing only root IDs and matching test/documentation expectations, not constraints or instance JSON. [#50](https://github.com/agent-primitives/suite/pull/50) consolidated the root compatibility exports into `compat.go` plus one package-level deprecation note without changing the API. The v0.7.0 tag points to that merge; [#51](https://github.com/agent-primitives/suite/pull/51) subsequently restored main's unstable draft IDs. Historical v0.5/v0.6 bundles stay byte-identical. New schema URLs are not available merely because source IDs or a tag exist: the schema release asset, a reviewed additive catalog update and verified Pages publication are separate required steps.

This remains pre-1.0. Suite document `1.0.0-draft`, evidence and policy versioning are not promoted by the module tag. `experimental/flow` still requires explicit selection; default readers refuse its critical extension. Offline graph/claim validation does not execute agents, authenticate the evaluator, enforce runtime policy or prove whole-flow success.

### Verification

The release tag points to reviewed merge `c268bbc747a5a6f7838595d961dc839a60c419cd`. Its [CI run](https://github.com/agent-primitives/suite/actions/runs/39658551570) passed all seven jobs, including native Linux/macOS/Windows identity/security, Go/conformance/race/vet/staticcheck, umask 077, TypeScript parity and documentation checks.

Fresh independent `GOWORK=off` checks on that exact merge also passed: uncached Go suites under umask 022 and 077 (1,229 named passes and all 22 required conformance cases, no skips), full race tests, static checks, cross-platform builds/test compilation, actual JS/Wasm security refusal, TypeScript parity, schema/release-tool selftests, docs/link/build and browser/accessibility checks. Native CI logs confirmed all 11 required Windows identity/security tests, including all five ACL cases, and all eight macOS cases without skips. The official v0.7.0 pre-tag schema check passed. Cross-compilation is not native execution, and these offline library checks are not downstream runtime qualification.

## [v0.6.0](https://github.com/agent-primitives/suite/releases/tag/v0.6.0) — 2026-10-20 — portable loose-directory identity and experimental flow

### Summary
- **Loose-directory identity is now portable.** Digests of unpacked suite directories no longer depend on host file permissions, umask or OS. Published artifacts are unchanged; rebuilding from a loose directory may produce a new digest.
- **Malformed inventories now refuse** (missing or null required fields).
- **Experimental, opt-in `kmx.flow.v1alpha1`** for two-step multi-agent flows; default readers refuse it.
- **Schemas move to `/schema/v0.6/`.** The v0.5 bundle is unchanged.
- **New dependency:** `golang.org/x/sys` (Windows security checks).

Who needs to act: if you package suites from loose directories, recompute digests and re-run evaluation for any artifact whose bytes change. If you only consume published artifacts, nothing changes.

### Portable loose-directory identity

This minor release intentionally changes loose-directory content identity. Host
permissions no longer select canonical content modes: ordinary files default to
non-executable `0644`, directories to `0755` with size zero, and supported Unix
symbolic links to `0777`. Explicit ToolProvider payload inventories supply their
declared modes; conflicting declarations refuse. A host `chmod +x` alone no
longer changes content identity or declares an executable.

This separates portable content metadata from host access controls, so the same
loose content does not acquire different identities from Unix permissions,
umask or synthesized Windows permission bits. Unsafe host access still refuses.
Unix access checks remain separate: group/world-writable regular files and
directories, including the selected root, and setid/sticky modes refuse.
Platforms that are neither Unix nor Windows refuse loose input with an explicit
unsupported-platform error. Windows loose trees require a current-user
owner, a protected root DACL and owner-only file/directory grants, with no broad
inherited access. Unsupported or unverifiable ACLs, filesystem security and
reparse-backed content refuse; caller-selected root aliases still resolve before
validation. Validation does not repair ACLs. Windows security checks add
`golang.org/x/sys v0.46.0` to the Go module dependency graph.

Loose `ContentDigest` values and supplemental content-record digests may change
even when file bytes do not. Recompute saved loose results with an explicitly
selected reader version; use v0.5.0 to reproduce its host-mode-dependent loose
identities. Older OCI archives with non-default undeclared modes may legitimately
differ from the new loose view.

**Published artifacts are untouched.** OCI layers retain their original tar
metadata and exact inventory comparisons. Existing byte/JCS/OCI digest
definitions, wire fields, signatures and evidence are not normalized or relabelled.
Verify an existing artifact from its original OCI representation, not a rebuilt
loose tree.

Rebuilds may produce new packaged bytes and digests. When they do, regenerate
affected descriptors and derived bindings/images, and obtain fresh evaluation,
approval and signing for the new exact subject as required. Do not edit old
receipts or reuse proof for a different subject. Consumers must migrate their
loose packagers and invalidate preparation caches when packaging output changes;
upgrading this library alone does not make a downstream packager portable.
The migration inventory in `docs/directory-identity.md` records these boundaries.
Native create → eval → lift qualification remains downstream work.

### Presence-sensitive inventory validation

Inventory decoding rejects missing or null required `path`, `type`, `mode`,
`uid` and `gid` properties in both loose and archived input. Explicit zero mode
and root ownership remain valid. Direct `encoding/json.Unmarshal` of an
`InventoryEntry` also rejects unknown and duplicate properties. These malformed
inventories could previously pass after decoding erased property presence; this
minor release closes that acceptance gap without changing schema constraints.

To repair malformed authored inventories, declare the required values and rebind
the variant digest, provider descriptor and all ancestor descriptors. Do not
rewrite published artifacts. Valid retained OCI artifacts and their identities
remain unchanged; malformed archived inputs may now refuse.

### Experimental opt-in flow

The `kmx.flow.v1alpha1` critical extension adds a bounded two-step flow contract
at `coordination/flow.json`. Explicit `ValidatePathFlowV1Alpha1`,
`ValidateDirectoryFlowV1Alpha1` and `VerifyEvaluationFlowV1Alpha1` APIs opt in;
default readers refuse artifacts carrying this critical extension. This validates
stored graphs and member evidence, not runtime delegation, approval enforcement
or whole-suite success. The frozen core draft grammar and evidence-v1 fields
remain unchanged. Stable graduation is tracked by
[#30](https://github.com/agent-primitives/suite/issues/30).

### Fresh v0.6 schema namespace

All 15 reference schemas use
`https://suite.agent-primitives.dev/schema/v0.6/` plus their actual filenames,
including `policy-v2.schema.json`, `administrative-policy-v2.schema.json` and
the new experimental `kmx-flow-v1alpha1.schema.json`. Select the complete v0.6.0 bundle in offline editor/validator registries; keep
historical bundles separate, without global old-to-latest aliases. The v0.5
bundle remains byte-for-byte frozen.

The namespace change does not change wire versions, media types, instance bytes
or validation constraints. Schema annotations also clarify the existing stable
core and experimental branches. The loose-reader identity change above is a
separate library behavior change, not a consequence of schema selection.
Minor releases freeze fresh IDs; patches must preserve their minor's entire
schema inventory and bytes, including IDs and whitespace. Canonical URL
availability requires the release asset, reviewed catalog and verified Pages
deployment; source IDs alone do not publish URLs. Validation remains offline.

### Stability and legacy-reader boundaries

The specification now names the intended wire-1.0 stable core and existing
experimental inference/execution branches. This is not a wire-1.0 release:
`1.0.0-draft` remains the Suite document version. Optional runtime profiles do
not establish runtime support, and unknown fields still refuse in closed readers.

The strict legacy draft grammar and acceptance baseline is documented at
`85da5faf6eaf400df2edeb401c194c11fe023b74`, distributed as v0.5.0 with schema
root-ID differences. New regression tests pin its version grammar and reader
boundary, including draft spellings that are not full SemVer. The loose-reader
identity change above is an explicit v0.6 exception; retained OCI identities and
historical proof remain authoritative. No dual-reader API, stable writer default
or automatic migration is introduced. The inventory-presence correction above
also tightens malformed-input acceptance; it does not redefine valid draft grammar.

### Verification infrastructure

Fixture helpers explicitly restore declared permissions after creation, so
restrictive umasks do not corrupt test inventories. CI adds a full umask-077
Go test leg, portable-identity checks on Linux/macOS/Windows and native Windows
security acceptance/refusal coverage. These are offline library checks, not
runtime or deployment qualification.

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
