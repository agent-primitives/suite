# Frozen legacy draft reader

## Selected baseline and published release

The strict legacy contract for `schemaVersion: "1.0.0-draft"` is frozen at
[85da5faf6eaf400df2edeb401c194c11fe023b74](https://github.com/agent-primitives/suite/commit/85da5faf6eaf400df2edeb401c194c11fe023b74).
Retain reading of documents accepted by that baseline indefinitely. The draft
literal is not an alias for the evolving stable contract, and legacy reading is
not a permissive mode that accepts every historical decoder bug.

The named published legacy-reader baseline is
[v0.5.0](https://github.com/agent-primitives/suite/releases/tag/v0.5.0), at
[e13c69ca25ee272cdeaeb497499d08c4967b345a](https://github.com/agent-primitives/suite/commit/e13c69ca25ee272cdeaeb497499d08c4967b345a).
Its production Go sources and module dependencies match the reviewed snapshot;
the reference schemas differ only in their root `$id` values. The release uses
`/schema/v0.5/` IDs, while the snapshot used historical IDs. These identify
schema bundles, not a different wire grammar or canonical identity algorithm.
Select the complete release-local bundle and validator out of band; the draft
literal alone cannot distinguish older releases with different acceptance.

This note selects the legacy baseline and records the retention plan. It adds
no dual-reader API, stable-document acceptance, writer-default change or release
tag. v0.5.0 is not a stable Suite reader or the future dual-reader migration
release. That later release still needs qualification before producers switch
away from draft output. See the [release policy](../CONTRIBUTING.md#release-policy).

## Preserve draft grammar and identity

Keep the baseline's closed fields, required/optional/null distinctions,
semantics, refusal behavior, canonical bytes and digest algorithms. A future
stable-only grammar correction does not apply retroactively to draft input.
In particular, exact provider versions use this draft grammar, not full SemVer:

```text
^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$
```

It accepts spellings such as `01.02.003`, `1.0.0-01`, `1.0.0-.`, `1.0.0+..`
and `1.0.0-alpha..1`, although they are not valid SemVer. It refuses valid SemVer
with both prerelease and build metadata, such as `1.0.0-alpha+build` and
`1.0.0-alpha.1+build.7`. Preserve both sides of this boundary for legacy input;
do not silently normalize these strings.

Leave released artifacts, tags, bytes, digests, signatures and evidence untouched.
Validation does not rewrite input. A conversion is a new artifact: update all
affected manifests and ancestor descriptors, repack, rebuild derived bindings or
images where applicable, re-evaluate and re-sign as needed. Evidence's own
version and standalone policy versions are independent; existing evidence does
not qualify a converted suite subject. This note changes no evidence checks.

## v0.6.0 loose-directory reader exception

The v0.6.0 minor release changes the loose-directory reader's content
metadata, not the published archive or JSON grammar. Loose regular files default
to non-executable `0644`; explicit payload inventories supply declared modes.
Host permission bits no longer enter loose semantic `ContentDigest` or supplemental
content-record identities. This is an explicit exception to frozen loose-reader
identity behavior: select v0.5.0 when reproducing its host-mode-dependent loose
results. Windows loose access additionally requires verified owner-only ACLs and
refuses broad inherited grants or unsupported security/reparse semantics.

Retained OCI artifacts still use their original tar modes, descriptors, JCS
identities, signatures and evidence. The reader MUST NOT normalize those archived
modes or silently rewrite an inventory to match new loose defaults. Rebuilding
source under the new policy is a new artifact where packaged bytes change; obtain
fresh proof for the new subject rather than reusing or editing old evidence.
The [comparison inventory](directory-identity.md) and [release notes](releases.md)
describe which identities change and which remain byte-for-byte authoritative.
No wire field or schema byte changes are part of this reader exception.

## Historical fixtures and baseline exceptions

A recorded offline probe on 2026-10-20 extracted the original `testdata/` trees
from the immutable tags below and called `ValidatePath` on each complete Suite
root using the unchanged baseline implementation. All 13 roots passed, with
file inventories and bytes unchanged:

| Release tags | Complete Suite roots checked |
| --- | --- |
| v0.1.0, v0.2.0 | `minimal`, `coordinator-workers` in each tag |
| v0.3.0, v0.3.1, v0.4.0 | `minimal`, `coordinator-workers`, `policy-binding` in each tag |

This is a one-off recorded result, not a Git-dependent CI test or an exhaustive
historical compatibility claim. It does not establish OCI packaging, registry
availability, runtime execution, authenticity or migration qualification.

When interpreting historical compatibility, distinguish these exceptions and
fixture-role limits:

- [#21](https://github.com/agent-primitives/suite/issues/21), published in v0.5.0,
  rejects Suite/ToolProvider extensions missing `critical`, present empty/null
  provider `variants`, and present null tool `outputSchema`. Those malformed
  inputs could pass older decoders after property presence was erased. Their
  old acceptance is not preserved. `ToolProvider` decoding also remains strict
  about unknown and duplicate properties.
- Agent extension handling is deliberately unchanged: missing `critical` remains
  accepted, explicit null is refused, and an unsupported critical extension is
  refused. Do not generalize the Suite/ToolProvider presence rule to Agents.
- `remote-mcp` and `tool-providers` contain provider, composition and construction
  examples, not complete Suite roots. Validate them in their documented roles;
  do not invent payloads or rewrite placeholder descriptors to make them into
  historical artifacts. [Detached evidence fixtures](https://github.com/agent-primitives/suite/blob/85da5faf6eaf400df2edeb401c194c11fe023b74/testdata/evidence/README.md)
  are synthetic and require their generated OCI context, not direct Suite loading.
- Earlier policy releases have their own compatibility boundaries, including
  v0.3.0's policy-v1 UTF-16 ordering/null-input corrections. See the
  [versioned release notes](releases.md).
  This probe does not claim every older standalone policy byte sequence matches
  the frozen reader; select an older contract explicitly when reproducing it.
- The later [test-only fixture helper fix](https://github.com/agent-primitives/suite/pull/33)
  restores declared modes under restrictive umasks. The reviewed snapshot and
  v0.5.0 precede that fix; it changes test construction, not artifact acceptance.
  Do not relax inventory or archive checks to compensate for a malformed fixture.

The baseline already includes v0.3.1's refusal of non-regular OCI files. Any later
security tightening needs an explicit compatibility exception documenting the
refused input, reason and affected releases; it must not silently redefine the
draft contract or rewrite retained artifacts.

## Regression coverage and later migration

`TestLegacyDraftVersionGrammar` pins schema acceptance/refusal and, through
exported `ValidatePath`, catalog-reference refusal and provider acceptance.
Both Go checks use the shared draft version grammar; this is not an exhaustive
test of every field using that grammar.
`TestLegacyDraftReaderBoundary` pins current root-version/unknown-field refusal
and preserves the received draft bytes. Existing presence, canonical-storage,
archive and full conformance tests remain part of the broader baseline.

When dual reading is introduced, run these vectors against its explicitly
selected legacy reader rather than rebasing their expectations on stable
producer defaults. Retain strict legacy reading while releasing compatible
readers before stable writers. Mixed-version graph implementation, version-aware
evidence checks, consumer graph-regeneration proofs and release qualification
remain separate work; this note and these tests do not deliver those gates.
