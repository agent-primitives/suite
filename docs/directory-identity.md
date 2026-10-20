# Directory identity and the v0.6.0 migration

The v0.6.0 loose reader separates portable content metadata from host access
permissions. It does not rewrite a stored artifact. The [specification](../spec.md#162-files)
and [release notes](releases.md) define the new behavior; [legacy reproduction](legacy-draft.md#v060-loose-directory-reader-exception)
requires selecting the reader version explicitly.

## Identity boundaries

A loose regular file defaults to non-executable `0644`. A declared ToolProvider
payload entry uses its explicit inventory mode; conflicting declarations refuse.
Directories use `0755`/size zero, and supported Unix symbolic links use `0777`.
Host `chmod`, Windows readonly attributes and the process umask do not select
canonical content modes. File types, bytes, digests, safe declarations and host
access checks still matter. Unsafe Unix write permissions still refuse; Windows
loose trees require a current-user owner, protected root DACL and owner-only
file/directory grants, with no broad inherited access. Unknown security semantics
fail closed. Validators do not repair ACLs or execute a declared executable.

An OCI layer is different: its existing tar metadata is authoritative. A stored
`0600` or `0755` mode remains exactly that, even when the loose default would be
`0644`. A mismatch against an archived payload inventory still refuses. Directory
and OCI content identities are equal only when their canonical metadata actually
matches; do not use the new loose view to recreate missing metadata from an old
artifact. JCS documents, their byte descriptors and OCI manifests are unchanged
unless the producer actually changes those bytes.

## Comparison inventory

The audit covers suite at [77584d2](https://github.com/agent-primitives/suite/tree/77584d2be13f2ea5a89f7d2af7d565eaed9bc131)
and kmx at [ae4c3711](https://github.com/kaimahi-agents/kaimahi/tree/ae4c371169684f17550a8bdd7fb7c5e9026fa98f),
including the callers of the following comparisons. Source links identify the
audited versions, not a promise that downstream code has already migrated.

| Location and comparison | Effect and action |
| --- | --- |
| suite [`loadDirectory`](https://github.com/agent-primitives/suite/blob/main/content.go), [`validateVariant`](https://github.com/agent-primitives/suite/blob/main/validate.go): loose payload metadata versus recorded inventory `Mode`, `Size`, byte `Digest`, link target and ownership | Mode now comes from the explicit declaration, with portable defaults outside inventories. Keep type/byte/digest/link/root-ownership and safe-declaration checks. Archive comparisons still use actual tar metadata. No host execute-bit inference is retained. |
| suite [`diffContentDigest`, `canonicalDiffContentEntry`, `diffContentRecord`, `DiffPaths`](https://github.com/agent-primitives/suite/blob/main/diff.go): aggregate and supplemental identities, then before/after comparison | Recompute externally saved loose `ContentDigest` values and diff results using the selected v0.6 reader. The library recomputes both inputs; no persisted loose `ContentDigest` reader was found. Old non-default archive modes remain meaningful, so loose/OCI differences can be legitimate. |
| kmx [`DiffSuites`](https://github.com/kaimahi-agents/kaimahi/blob/ae4c371169684f17550a8bdd7fb7c5e9026fa98f/internal/kmx/app/suite_diff.go): delegates to suite `DiffPaths` | Inherits the changed loose/loose and loose/OCI results when the consumer upgrades. No independent stored loose content-digest cache was found. Document that boundary at the consumer upgrade; do not silently compare a saved old loose result as if it used the new reader. |
| suite manifest loaders, [`validateFileRef`, `rawVariantDigests`](https://github.com/agent-primitives/suite/blob/main/validate.go), composition/dependency pins: source versus recorded JCS or exact byte descriptors | Permission normalization alone does not change these digests. If an authored inventory mode changes, regenerate variant identity, provider descriptor, dependency/composition pins and ancestor suite descriptors. Never repair historical declarations in place. |
| kmx [`ResolveSandboxPlan` and its loaders](https://github.com/kaimahi-agents/kaimahi/blob/ae4c371169684f17550a8bdd7fb7c5e9026fa98f/internal/kmx/agentsuite/builder.go): `ValidateDirectory`, root bytes before/after, provider/variant pins, child byte descriptors | Directory acceptance changes; byte/JCS digest definitions do not. Its `SuiteHash` is a root-document JCS identity, not suite's aggregate `ContentDigest`. Do not invalidate these recorded byte digests merely because the loose reader changed. Rebuild derived output if declarations or packaged bytes change. |
| kmx [`workspace/native.go`](https://github.com/kaimahi-agents/kaimahi/blob/ae4c371169684f17550a8bdd7fb7c5e9026fa98f/internal/kmx/agentsuite/workspace/native.go), [`prepare.go`](https://github.com/kaimahi-agents/kaimahi/blob/ae4c371169684f17550a8bdd7fb7c5e9026fa98f/internal/kmx/agentsuite/workspace/prepare.go): selected authored-input fingerprint, cached fingerprint/name, prepared file-byte comparisons | This is a separate consumer-owned fingerprint/cache contract. A suite-only reader change does not automatically invalidate it. The later kmx packaging migration must bump its renderer/layout version when output changes, prepare a new artifact, and obtain new evaluation for the new artifact subject. Never let an old cache silently stand in for differently packaged output. |
| kmx [`sourceRevision`, `matchCommittedTree`, `matchWorkspaceTree`](https://github.com/kaimahi-agents/kaimahi/blob/ae4c371169684f17550a8bdd7fb7c5e9026fa98f/internal/kmx/app/agent_suite_source.go): captured source bytes and Git executable modes against HEAD objects | Git provenance is not portable suite content identity. Keep exact byte/Git-tree claims separate; native Windows follow-up must not invent a host execute bit to assert a clean Git-tree match. A changed provenance result is not authority to alter artifact modes or reuse evidence. |
| kmx [`oras/writeArchive`](https://github.com/kaimahi-agents/kaimahi/blob/ae4c371169684f17550a8bdd7fb7c5e9026fa98f/internal/kmx/agentsuite/oras/directory_push.go): loose-file execute bits become tar modes, compressed archive descriptor then OCI descriptor | This producer still needs a consumer-side change: use default non-executable modes and explicit declarations instead of host execute bits. That follow-up belongs to the kmx v0.6/native PR; this suite PR does not make the existing packager deterministic. Changed output means a new layer descriptor and a newly packaged OCI artifact, never an alias for the old digest. |
| suite [`VerifyEvaluation`](https://github.com/agent-primitives/suite/blob/main/evidence.go), kmx [`preparedLayout`, `PushLayout`, `PushLayoutRegistry`](https://github.com/kaimahi-agents/kaimahi/blob/ae4c371169684f17550a8bdd7fb7c5e9026fa98f/internal/kmx/agentsuite/oras/prepared_push.go), artifact readers and prepared-layout descriptor checks | These bind exact OCI descriptors/evidence subjects, not loose host permissions. Existing artifact verification is unchanged. Previously passing evidence cannot qualify a newly packaged subject; evaluate and sign the new subject as required without rewriting old proof. |

Private cache/receipt/config ACLs and permissions, live Kubernetes object
fingerprints and admission observations are not portable content identities.
Removing host modes from loose identity does not remove those independent
security or ownership checks.

## Upgrade sequence

1. Retain published artifacts and their existing evidence unchanged. Verify them
   from their original OCI representation, not a newly reconstructed loose tree.
2. Upgrade the suite consumer to the reviewed v0.6 release once maintainers publish
   it. Select an older reader explicitly when reproducing historical loose results.
3. Migrate the consumer's loose packager to declaration/default modes. If output
   changes, invalidate the appropriate consumer preparation cache/version and
   rebuild: **rebuild means a new artifact**.
4. Recompute changed descriptors and derived bindings/images. Obtain fresh passing
   evaluation, approval and signing for the new exact subject where required.
5. Do not relabel old digests, edit saved receipts or infer that previous evidence
   authorizes a different artifact. Native create → eval → lift qualification is a
   separate kmx follow-up, not established by these offline identity tests.
