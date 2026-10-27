# Shared format conformance corpus

These inputs and expected results are shared data for implementations of the
AgentSuite format. Go consumes the committed files directly. Another implementation
must read the same files, not translate them into a second set of fixtures.

The initial cases were extracted from the Go tests at commit
`2a21ec3b055dde159b43b58cef70b4f1ea0b17c6`. This is a foundation, **not complete
Go validator coverage**. Moving those initial expectations changed no schema
bytes, production acceptance rules or digest algorithms.

## JSON documents

Every line of [json-cases.jsonl](json-cases.jsonl) is an RFC 8785 canonical JSON
object, and the file ends with LF. Fields are:

| Field | Meaning |
| --- | --- |
| `name` | Unique case identifier |
| `target` | Decode as an untyped JSON value (`json`), `Descriptor` (`descriptor`) or `Platform` (`platform`) |
| `input` or `inputHex` | Exactly one: the JSON string's decoded UTF-8 bytes, or hex-encoded literal bytes for invalid UTF-8 |
| `valid` | Expected strict-decoding acceptance, not just JSON syntax validity |
| `canonical` | For accepted cases only, the exact JCS output, represented as a JSON string |
| `size` | For accepted cases only, canonical UTF-8 byte length, not character count |
| `digest` | For accepted cases only, lowercase `sha256:` of those canonical bytes |

Decode input strictly before canonicalizing. This includes duplicate keys, Unicode,
lossy integers and closed document fields. Referenced stored manifests have further
canonical-storage requirements; accepting a formatted JSON value here does not
mean its raw bytes satisfy a descriptor.

Sources are [core JSON tests](../../core/json_test.go),
[shared codec tests](../../internal/jsoncodec/json_test.go) and the Unicode,
number and depth cases in [artifact validation tests](../../internal/artifact/validate_test.go).
The corpus includes depth 100 acceptance, depth 101 refusal and 1,025-object-member
refusal. Larger document-size/member-count tests and codec-specific lexeme/sentinel
checks remain in Go.

[variant-cases.jsonl](variant-cases.jsonl) has `name`, `input`, `canonical` and
`digest`. Its input is a provider-shaped JSON object containing one raw variant;
this tests **variant identity**, not validity of a complete provider. Replace only
the variant's `variantDigest` value with the empty string before JCS serialization
and hashing. Optional false, empty and zero-valued members must not disappear.
The two expectations come from `TestRawVariantDigestsPreserveExplicitZeroValues`.

The [policy decode corpus](../../policy/testdata/decode-cases.jsonl) remains the
shared source for policy acceptance, effective canonical bytes and framed effective
policy digests. Do not confuse those effective digests with authored-policy content
pins. The selected complete [schema bundle](../../schema/) is also shared;
validation must never fetch schemas or meta-schemas over the network.

## Bundled variants, dependencies and selected collisions

[bundle-cases.json](bundle-cases.json) freezes **47 actual Go fixture promotions**:
29 variant/inventory, 10 dependency-closure and 8 selected-collision rows. Each
stores complete provider JSON bytes and normalized portable entry snapshots,
including their directory/archive source policy. Snapshots precede directory-mode
binding; they do not record host uid/gid or umask-dependent access permissions.
The named Go entry point is explicit. Twenty complete directory-fixture rows also
run through full `ValidatePath` with literal provider bytes and refreshed ancestors.

Both languages consume the same bytes and snapshots. Positive chain/diamond rows
pin DFS order; cycles, exact platform/digest selection, a stale incoming edge to
an already visited node, metadata mismatches and untracked payloads are refused.
Identical installation overlap is legal; component/path are not installed-entry
metadata. Unselected variants are not globally combined for collision checking.
Directory-source declared modes bind every inventory and conflicting declarations
are refused even across variants that are not coinstalled. Archive modes are exact.

This is **bundled-subsystem parity only**, not Python whole-package validation.
Graph-only rows use synthetic variant pins like the existing Go closure tests;
a cryptographic dependency cycle cannot carry self-consistent raw hashes. They
exercise only the recorded closure/collision entry point, not variant identity.
Three negative graph rows are refused by the owning Python schema before the
local helper (duplicate dependency, ambiguous platform, non-root owner); this is
not claimed as direct helper coverage. Corpus bytes are authoritative frozen inputs,
not regenerated during CI. The ignored one-shot fixture promoter is not a shipped
regeneration tool. Native/no-skip required gates and installed-wheel coverage apply.

## Private profile and composition graph prerequisites

[graph-cases.json](graph-cases.json) freezes **71 distinct complete actual-Go inputs**:
portable entry metadata and exact base64 bytes for every regular fixture file.
All 71 run through the real ordinary Go graph phases, excluding only stored
policy/evaluation semantics. **69 complete directory snapshots also replay full
`ValidatePath`**; two archive metadata controls keep archive mode authority.
The phase and refusal are frozen, and full-path cases must reach the intended
refusal rather than an incidental stale ancestor. Required normal/native no-skip
passes enforce nonempty populations. Python consumes the same snapshots, not a
separately translated fixture generator.

Coverage includes minimal/coordinator/remote/bundled/standalone/shared-provider
seeds, two runtime profiles and their 13 graph refusals, current build/runtime and
composition pins, exact platform/harness agreement, explicit false/presence,
execution inputs, sorted/exact provider resolutions, invocations, per-agent
compositions, standalone dependency collisions, inward retention and exact
capabilities (including retained/unselected providers). Original Go tests remain
enabled. Synthetic cryptographic dependency cycles remain isolated closure cases
in the bundle corpus; they are not claimed as fully pinned package examples.

Additional Python tests use schema-valid distinct objects for duplicate execution
names/environments, image platforms and graph selection keys; they assert intended
codes and source fields. Full-string checks preserve Go refusal of final-newline
identities and HTTP paths even where JSON Schema's `$` anchor can match before a
final newline. Image checks preserve Go registry normalization and repository/host
bounds, and strip/check port digit length before integer conversion without adding
an interpreter-dependent format limit.

Regular payload bytes in this corpus are test replay transport, not broader
production retention: existing streamed metadata-only payload tests still apply.
Installed wheels exercise both OCI graph collection and the two-profile snapshot.
This remains **private graph-prerequisite validation**, not a finished public
package reader or verified root identity. Policy/evaluation semantics stay pending;
no model, evaluation, image or runtime is executed and nothing is fetched.

The `standalone` snapshot also covers provider-only inward retention; it is counted
once, not repeated under an alias. The existing `minimal` snapshot is also the
explicit `Composition.toolProviders: []` control for an agent with no providers.
Two distinct shared descendants omit that property or set it to null, with exact
canonical child bytes and current root descriptor size/digest. Both languages run
all three; Go also replays each complete package through `ValidatePath`. Python's
owning schema still refuses omission at the composition object (`schema.required`)
and null at `/toolProviders` (`schema.type`).

Go now refuses missing/null `toolProviders` at the authored `Composition` decoder,
aligning with the unchanged owning schema. **An empty array remains valid**; this
does not add a nonempty requirement or change `CompositionRef`. This Go acceptance
tightening belongs to the next minor/draft, **not a v0.7.x patch**. Authors without
provider resolutions must write `"toolProviders": []` (Go callers should initialize
an empty, non-nil `[]core.ResolvedToolProvider`). Recanonicalize changed composition
bytes, refresh the root composition descriptor's size/digest, then refresh outer
pins/identities if packaging or publishing the changed root.

Python object-array uniqueness uses structural
JSON keys instead of all-pairs object comparisons. Deterministic regressions count
comparison/key work through wide execution inputs and resolved providers, while
stock-validator parity checks retain boolean/numeric distinctions, numeric equality,
object-key independence, array order and exact diagnostic locations. Arrays with no
top-level object keep stock sorting, including its nested-sequence corner cases.
Schema bytes
are unchanged. Bundle-local validation views preserve the extension across owned
2020-12 references; mixed/nested dialects or metadata-sensitive references keep
stock validation. This is not an aggregate CPU or worst-case hash-work guarantee.

## Local declarations and private typed documents

[declaration-cases.json](declaration-cases.json) freezes 23 exact JSON byte inputs:
four accepted and 19 refused. Go checks each through strict decoding/local
Suite/Agent/remote-provider declaration validation **and** a correctly repinned
full package. Python decodes the same bytes into private typed records and checks
local declarations. The corpus covers unsafe environment names, duplicate names
and effects, invocation declarations, remote headers, authorization and extensions.

This is declaration-scope evidence, not full inventory, dependency, invocation
closure, composition, policy or evaluation coverage. Go can join multiple errors;
these cases compare acceptance and intended field context, not identical diagnostic
ordering or text. Both CI gates require named no-skip passes. Existing presence and
string-bound cases also run through Python's typed decoder. Suite/provider
extensions refuse a present-empty digest per their schemas; Agent extension items
retain their existing separate rules, including an empty optional digest.
This Go acceptance tightening belongs to the next minor/draft, not a v0.7.x
backport. Omit an empty optional extension digest or supply a valid SHA-256,
then canonicalize the affected manifest and refresh its ancestor pins.

Private pin tests distinguish noncanonical roots from canonical pinned children,
literal from JSON hashes, retained metadata from unretained literal files, and
identity/duplicate/refusal paths. The native directory and OCI pipelines and
installed-wheel smoke reach the same private document prerequisites; none returns
a verified graph or exposes a public package loader.

## Authored-document presence and empty files

[document-shape-cases.json](document-shape-cases.json) freezes 32 exact JSON byte
inputs: five valid controls, two existing refusals and 25 corrected Go/schema
conflicts. Both languages decode the same base64 bytes. Go installs the child in
a real package, rebinds ancestors without erasing malformed fields, checks that
stored bytes are unchanged, and runs full validation. Python runs the complete
unchanged bundled schemas. Refusals check field context; both jobs require named,
no-skip passes, including native Go directory validation on all three platforms.

The 25 corrections cover explicit nulls, present-empty model/environment values,
forbidden authored platform variants and an omitted empty-file inventory size.
Checks stay at authored boundaries, not the shared OCI codec. Agent extension
items keep their existing rules; referenced tool-schema JSON may still contain
literal nulls. Direct and canonical Go serialization now emit `size: 0` for empty
regular inventory files; nonempty files, directories and links retain their
canonical representation. Literal JSON/hash goldens and a typed package
roundtrip verify variant identity and refreshed provider/catalog/Suite pins.

This is a next-minor acceptance and emitted-byte change, not a v0.7.x patch.
Omit invalid null/empty optional fields, remove authored platform `variant`, and
include file size even when zero. Rebuild canonical variant and ancestor pins:
Go-produced packages with empty files get new digests. kmx picks this up when it
next moves its suite version. No schema bytes or historical bundles change.
Existing tracked fixtures contain no affected empty-file inventory entries;
the deliberately malformed regression bytes retain their valid old pins so a
pin error cannot hide the intended shape refusal.

## Catalog-reference identity

[catalog-reference-cases.json](catalog-reference-cases.json) freezes five literal
Suite root inputs: baseline and arbitrary valid identifier controls, plus missing,
empty and invalid `toolProviderCatalog.id` refusals. The bytes come from the
`suite-baseline` Go fixture in [document-shape-cases.json](document-shape-cases.json),
changing only that root ID. Child bytes and their descriptor pins are unchanged;
tests do not regenerate the corpus.

Go strict decoding alone accepts all five inputs, including the missing ID.
The existing `loadToolProviders` semantic loader owns the identifier refusal;
the Go runner checks strict decoding plus that loader and full `ValidatePath`
on a native secured directory fixture. Python checks the identical bytes against
the unchanged Suite schema in the closed offline Bundle. It asserts source
`agentsuite.json`, code `schema.required` at `/toolProviderCatalog` for a missing
ID, and `schema.pattern` at `/toolProviderCatalog/id` for empty or invalid IDs.
Named required passes and no-skip gates include normal and native Go CI.

This tightens Go acceptance to the existing draft schema and requires the next
minor release; do not backport it as a patch. Set the root reference ID to any
identifier matching the schema, not a fixed catalog name. The catalog body has
no ID, so no body-ID equality is required. Migration changes the Suite root
identity and any enclosing package pins; unchanged child pins need no refresh.
No schema bytes, Python acceptance rules or Go APIs change.

## String length bounds

[string-length-cases.json](string-length-cases.json) supplies literal field values
and expected acceptance for 21 agent/provider cases. Both languages apply the same
values to existing fixtures: Go exercises package/provider validation, while
Python checks the exact bundled schemas. Agent descriptions accept 4,096 Unicode
code points and refuse 4,097, including multibyte, astral and combining text;
there is no byte-count or grapheme-count substitution. Remote header names accept
128 ASCII token characters and refuse 129. Present ABI versions, inventory
components and link targets cannot be empty; `omit: true` removes an optional key
rather than supplying an empty string. Omitting those optional keys stays legal.

These tighten Go acceptance to existing draft schema constraints without changing
schema bytes. Other pre-existing byte-based path/evaluation limits are unchanged;
this corpus does not claim complete Go/schema acceptance parity.

For existing inputs, shorten descriptions/header names that exceed these bounds
and omit optional ABI version, component or link-target keys instead of authoring
empty strings. Canonicalize changed manifests and refresh affected variant,
provider, catalog and Suite descriptors bottom-up. This acceptance tightening
requires the next minor release; do not backport it as a v0.7.x patch.

## Image references

[image-reference-cases.json](image-reference-cases.json) contains named `imageRef`
strings and the general Go image-reference helper's expected `valid` results.
Go and Python schema tests consume the same 48 cases for `runtimeBase` and
`harness`. Optional `schemaValid` distinguishes the narrower authored syntax from
the helper's value-level contract; otherwise schema acceptance matches `valid`.
Actual Go build-profile validation must satisfy both contracts. Its shared test
exercises 96 field-specific cases and 12 fully repinned package paths, with required
native/no-skip gates. Uppercase IPv6, DNS names containing `--` and mixed single
repository separators are positive controls.

Bracketed authorities require hexadecimal IPv6 groups: eight full groups or one
`::` replacing at least one group, with 1–4 digits per group in either case.
Optional decimal ports must be 1–65535; leading zeroes are accepted. IPv6 repository
paths are limited to 255 bytes, excluding the authority and digest. Missing/extra/
empty brackets, malformed addresses, dotted tails, zones, invalid ports, trailing
newlines and tag-only references are refused. The schema's `not` guard enforces
that path limit and compensates for differing final-newline anchor behavior in
Go and Python. Existing schema DNS-authority and path-separator constraints are
unchanged. The authored Go build-profile boundary now also refuses uppercase DNS
registry spelling, `__` repository separators and repeated repository hyphens.
The general `core.ValidateImageReference` helper deliberately remains unchanged;
its broader OCI-name acceptance is not authored build-profile acceptance.

Published schema bundles, IDs and canonical-identity algorithms are unchanged;
the earlier draft IPv6 schema correction and this authored Go acceptance tightening
belong to a future minor release, not a v0.7.x patch or change to a frozen bundle.
Existing build profiles using the three newly refused spellings must select a
schema-valid registry/repository reference for the intended image, canonicalize
the changed build profile and refresh its Suite descriptor size/digest, followed
by any outer package pins. Lowercasing a DNS name may preserve the registry's
meaning, but changing a repository name does not create or move an image; consumers
must use a reference that actually exists. No fixture digest changed in this fix,
and no tag, release note or publication is performed here.

## Directory content loading

[directory-cases.json](directory-cases.json) fixes the portable path/link rules,
case-collision outcomes, metadata-retention boundaries and retained-byte budget.
The `limits` object records the shared numeric caps. A path may use literal
`value` or invalid UTF-8 `hex`; these are lexical tests, not a promise that every
host filesystem can represent the name. Folding matches the selected Go/x-text
reference, not normalization or Python's interpreter-dependent default folding.

[directory-access-cases.json](directory-access-cases.json) provides literal file
bytes as hex and named fixture operations with expected `valid` results. Both
implementations construct the same bare directory input, apply the operation,
and compare acceptance plus raw hashes, retained bytes and portable modes.
`platform` selects applicable POSIX/Windows operations; no native cell is skipped.
Only test setup assigns temporary permissions/ACLs or creates root aliases and
junctions. Production must refuse unsafe inputs rather than repair them.

This is content I/O, not package/schema/graph validation: empty directories and
unparsed JSON can pass this layer. Payloads and Markdown are streamed but not
retained; only lowercase `.json` files up to 4 MiB count toward retained metadata.
Root aliases resolve once, descendants stay under opened directory capabilities,
and links are never followed. File/observed-directory replacements detected while
opening and file-size changes while reading are refused. The loader does not
promise an immutable or coherent snapshot against concurrent same-size writes.

## Packages and OCI layouts

[packages.json](packages.json) is an array with unique `name`, `path`, `form`
(`directory` or `oci`) and `valid` fields. Resolve each path relative to this
directory. Accepted rows contain:

- `contentDigest`: the existing Go semantic-diff aggregate identity. It is a
  **test-only compatibility expectation**, not an additional normative format
  identity or public Python SDK API. Its serialization is Go JSON, not JCS.
- `rootDigest`: for directory rows, the JCS digest of `agentsuite.json`.
- `manifestDigest`: for OCI rows, SHA-256 of the exact OCI manifest blob bytes.

Unused identity fields are empty strings. Refused rows have no expected identities.
Expected outcomes are language-neutral; Go checks its diagnostic text separately.
Every row must be exercised, including refusals. The runners reject empty/truncated
case sets and duplicate names; CI requires their named passing results.

Directory rows reuse [minimal](../minimal/),
[coordinator-workers](../coordinator-workers/), [policy-binding](../policy-binding/)
and [rich-evaluations](../rich-evaluations.README.md) in place. The rich fixture adds
four ordered cases with judge, tool and RE2 constraints and repeat policies.
`minimal` is byte-for-byte identical to the former inline identity fixture,
including its indented root and the final LF in its instructions. Do not normalize
or reserialize copied files.

The four [stored OCI layouts](oci/) freeze the inputs previously produced by
`identityTar` and `writeTestOCILayoutTar` in the Go tests:

- `minimal-0644`, `minimal-0600` and `minimal-0755` vary the archived instruction mode
  and retain the existing three aggregate-identity goldens.
- `inventory-mode-mismatch` declares an executable provider payload but archives it
  as mode 0644; validation must refuse the inventory/payload mismatch.

Each is an **OCI directory layout**, not an archive-file API input. Its content blob
contains the gzip/tar layer. Blob filenames, sizes and hashes bind exact stored bytes.
These files are not regenerated during tests or CI. A writer must produce a
conforming archive, but need not reproduce another compressor's byte stream.
Byte-identical copying/publishing must retain the supplied manifest and layer bytes.

[Testdata Git attributes](../../.gitattributes) prevent checkout conversion of literal
instructions and blobs on Windows. Copy fixtures to temporary directories before
changing modes or ACLs. Go applies explicit modes and its existing native security
fixture helpers; umask 077 must not alter declared or archived identity. A consuming
implementation must reproduce the same access checks rather than repair unsafe
production inputs.

## Raw gzip/tar content layers

[`archive-cases.json`](archive-cases.json) stores 94 exact gzip inputs as base64:
40 accepted layers with complete raw-entry snapshots and 54 refused layers.
Both private readers consume those same bytes. Cases cover tar framing and modes,
link ordering, legacy types, effective PAX/GNU names, timestamps, sparse files,
extension byte limits and gzip members/trailers. Four inputs preserve the stored
OCI layouts' content blobs; the inventory-mode mismatch remains readable content,
not a successful package validation. No fixture is extracted or regenerated in CI.

The Go test-only oracle also checks generated byte-level Python probes. Corpus
population/name/type guards and required no-skip passes prevent empty selections
from qualifying a reader. This raw-layer coverage does not include package schemas, graph closure or
verified Suite root identity.

## OCI envelopes and blobs

[`oci-cases.json`](oci-cases.json) adds 112 named envelope/blob cases, 29 accepted
and 83 refused. `layout` selects one stored layout above; optional `files` maps
relative paths to replacement literal base64 bytes, or null to remove a file.
Accepted cases bind `artifactDigest` to the exact manifest bytes and `archiveCase`
to the complete entry snapshot in `archive-cases.json`. Both languages copy the
layout, apply those exact bytes and run their private OCI loader. The graph-invalid
inventory fixture remains accepted as raw I/O, not as package validation.

The shared cases cover Go's `TestEmptyOCIConfigIsExact`, descriptor URL/data and
extra-index refusals from `validate_test.go`, plus typed null/absence, closed fields,
media types, subject, annotations/platform, embedded byte arrays/base64, missing and
tampered blobs and noncanonical manifest identity. Native special-file/root-alias
cases remain in `oci_special_unix_test.go` and Python native tests, because JSON
bytes cannot represent host links, FIFO races or Windows handles. Generated Python
probes also call the actual Go loader through its test-only oracle; runtime Python
never invokes Go. Population guards and named CI passes apply to both languages.

Only indexed manifest descriptors have the 1 GiB aggregate envelope cap; JSON
reads have a separate 4 MiB cap. Compressed layers stream without a new envelope
byte cap and retain the existing archive limits. Memory/per-record bounds do not
establish an aggregate CPU or total-input budget.

## Literal bytes and root identity anchors

[literal-cases.json](literal-cases.json) holds six compact byte vectors:
empty/non-UTF-8 instructions, instructions over 4 MiB, noncanonical schema JSON,
and input/output schema JSON over 4 MiB. Arbitrary `.data` paths and an oversized
`.json` path distinguish literals from bounded canonical metadata. Exact bytes
are base64-decoded `prefix + block * repeat + suffix`; size and SHA-256 are frozen.
The 5 MiB expansion guard is test transport only, not a package-format limit.

The base is `writeMinimalSuite`, identical in root identity to the `minimal` row
of [graph-cases.json](graph-cases.json), not the separate minimal fixture folder.
Instruction cases replace `agents/writer.json`'s reference and repin agent/root.
Schema cases retain that agent, copy all four `remote-mcp/schemas` files unchanged,
and install canonical `remote-mcp/tool-provider.json` at
`tool-providers/search/1.0.0/tool-provider.json`. Replace its first tool's target
reference, append its manifest reference to the empty catalog, then canonically
repin provider/catalog/root. Keep the old literal files and composition unchanged.

Go computes each frozen `rootDigest` only after ordinary directory and OCI
`ValidatePath` both accept. These are shared byte vectors and root anchors, not
complete package snapshots or evidence of a finished Python package reader.
No corpus regeneration occurs during tests.

## Ordinary reader snapshots

[reader-cases.json](reader-cases.json) freezes 30 complete directory snapshots
from actual Go helpers at `d753475d3313507bb3297d06b28ec373287e3791`:
seven accepted and 23 refused. It reuses the graph transport with every regular
file's literal base64 bytes, portable 0644/0755 modes and zero ownership.
Go checks literal hashes, runs ordinary policy/evaluation validation on the
same entries, replays all 30 through full `ValidatePath`, and replays the seven
accepted inputs through OCI with authored portable modes. Refused rows freeze
the exact first diagnostic; additional unvisited-file diagnostics may be
map-ordered. Every child and ancestor pin is frozen, including raw `50.0` and
`1e0` integer-field refusals that must not be canonicalized away.

Cases cover stored policies/evaluations, namespace ownership, run bounds,
assertion identity, RE2 lookahead refusal, multibyte byte limits and Unicode.
Ten selected frozen documents also run against Go's actual reference schemas:
C0 separators and VT/NEL/NBSP/BOM satisfy Go's `\S`; semantic blank-input
checks separately refuse VT/NEL/NBSP. Final-newline agent/case/judge identities
fail both schema and ordinary validation. The rich positive includes a U+2028
rubric, ordinary RE2, a judge and repeats. Original graph/literal corpora remain
unchanged. This selected corpus does not replace the remaining Go tests or
prove model execution, complete regex equivalence or native-host parity.

## Policy/evaluation ordinary-case inventory (base d753475d)

[reader-semantic-cases.json](reader-semantic-cases.json) adds **112 complete
snapshots: 18 accepted, 94 refused**. These are frozen once from the actual Go
helpers and original table mutations, not independently translated Python
fixtures. Every row carries a base-qualified `origin`: the original Go test
function and table-row name, or the current ordinary-validator boundary under
test. Both runners consume these literal bytes. No fixture generation runs in
CI. All original Go tests remain enabled.

The Go gates are `TestSharedReaderSemanticCases` (every row through
`validateContent` and full `ValidatePath`) and
`TestSharedReaderSemanticOCIPositives` (all 18 accepted snapshots through OCI,
with authored 0644/0755 modes). The graph transport includes every regular
file's bytes, even where production intentionally does not retain Data.
Names, counts, explicit fields/nulls, sorted entries, byte size/digest, complete
directory roots and base provenance are checked. Refusals freeze the first
complete owning-agent diagnostic, not its map-ordered namespace tail.
For namespace-only failures there is no stable first Go diagnostic: both the
promoter and test select the lexical-first complete diagnostic instead.
This exception changes no acceptance rule or product diagnostic.

### Evaluation inventory

Sources: [evaluation_test.go](../../internal/artifact/evaluation_test.go) and
the current [ordinary validator](../../internal/artifact/evaluation.go).
The following mapping covers every original function/table row. A prefix means
**all** original rows in that family, with the exact row name in each snapshot's
`origin`, except the explicitly reused rows listed here.

| Original Go test/family | Shared mapping |
| --- | --- |
| `TestEmbeddedEvaluationsAcceptDirectoryAndOCI` | `eval-default-suite`, including portable OCI replay |
| `TestEvaluationReferenceSchemas`: accepted index/agent; maxCases 129, maxCaseBytes 0, extra results, null evals | Existing packages `coordinator-workers`; `eval-graph-invalid-count-limit`; shared typed evaluation/schema tests for the two isolated schema constraints; `eval-strict-unknown-field` is the ordinary closed-record family; `eval-binding-null`. These isolated schema tests are not additional package acceptance promises. |
| `TestEmbeddedEvaluationsRejectInvalidGraph` (14 rows) | All `eval-graph-*` origins (12); original “wrong agent” → reader `eval-agent-mismatch`; “unreferenced case” → reader `eval-orphan-file` |
| `TestEmbeddedEvaluationAgentBinding` (5 rows) | All `eval-binding-*` origins, including null, wrong path, stale digest, multiple indexes and unbound tree |
| `TestEvaluationAssertionsMatchSchemasAndSemantics` (24 rows) | All `eval-assertion-*` origins: all eight positives and all sixteen refusals, with original assertion bytes |
| `TestEvaluationCaseRunPolicy` (10 rows) | All `eval-runs-*` origins (8); “min passes without runs” / “min passes exceeds runs” → reader `eval-minpasses-without-runs` / `eval-minpasses-exceeds-runs` |
| `TestEvaluationCaseStrictness` (6 rows) | All `eval-strict-*` origins (4); “duplicate assertions” → reader `eval-duplicate-assertion-ids`; “wrong case id” → reader `eval-case-filename` |
| `TestEvaluationIdentityCommitsToCasesAndOrder` | `eval-stale-order`, `eval-repinned-order`; reader rich/shared packages bind edited case bytes. Diff affected-agent/reason/identity-report assertions are diff APIs, not public-reader results. |
| `TestEvaluationJCSIdentityIgnoresJSONFormatting` | `eval-default-suite` and shared JSON canonical-formatting goldens; the original Go unit comparison remains enabled. The producer canonicalized both snapshots to identical bytes/metadata, so no duplicate snapshot is counted. |
| Current evaluation.go boundary probes, beyond original tables | `eval-source-*`: index/case version and media; reference media/size; invalid case digest; empty assertions; known null operand; rubric control. Pins are refreshed to reach the intended layer. |
| Additional Unicode, byte-length, identity and numeric-lexeme probes | Existing reader30 origins; [regex-cases.json](regex-cases.json) has 702 Go syntax probes including wide-class resource and class-range/POSIX regressions |

### Authored-policy binding inventory

Source: [policy_binding_test.go](../../internal/artifact/policy_binding_test.go).

| Original Go test/family | Shared mapping |
| --- | --- |
| `TestPolicyBindingAcceptsAuthoredPolicies`: v1, v2, deny all | Reader `reader-rich` contains original bindingV1 bytes; `policy-v2-ipv4` / `policy-v2-empty-allowlist` contain original bindingV2 / bindingDenyAll bytes. Existing typed codec tests retain round-trip checks. |
| `TestPolicyBindingRejectsReferenceShapes` (20 rows) | All `policy-ref-*` origins, including missing/null/unknown descriptor fields, path, size, digest, media and version binding. Its final unrelated unknown-agent-field check is the shared closed-record JSON family (`platform-unknown-field`) and existing typed agent tests. |
| `TestPolicyBindingRejectsInvalidDocuments`: empty/relative v1 paths, missing capability, unknown v1 field, v1 network | Shared wire rows `empty denyWritePaths`, `relative path`, `missing requiredCapabilities`, `unknown field`, `v1 with null network`; reader `policy-v1-empty-paths` also exercises ordinary package rejection |
| Same: missing v2 network, null list, wrong protocol, unknown endpoint, v2 filesystem | Shared wire rows `missing network`, `null egressAllow`, endpoint UDP/extra-field rows, `v2 with empty denyWritePaths` |
| Same: fractional port, enormous exponent | Shared wire invalid-port precise-fraction and out-of-range exponent families (including 443.0000000000000000000001 and 1e400); raw numeric lexemes are preserved |
| Same: wrong version media, noncanonical raw descriptor, not JSON | `policy-document-v2-wrong-version-media`, `policy-document-noncanonical-raw-descriptor`, `policy-document-not-JSON` |
| Same: unsupported version, duplicate field | Shared wire `unknown version`, `duplicate key`; shared JSON strict parsing also applies before policy decoding |
| `TestPolicyBindingChecksDescriptorsBeforeDecoding` (5 rows) | All `policy-before-decode-*` origins; malformed `{` remains the target bytes, so the frozen refusal proves descriptor checks precede decode. `policy-document-not-JSON` is the correctly pinned decode-refusal control. |
| `TestPolicyBindingRejectsUnownedContent`: missing, cross agent, outside namespace, orphan file, nested file, stale policy bytes, noncanonical canonical descriptor | All seven `policy-unowned-*` origins |
| Same: extra directory | Reader `policy-orphan-subdirectory` |
| Same: oversized policy | Boundary `policy-oversized`: 4,194,305 spaces, exact raw descriptor and Go-generated ancestor pins; compact body directive, not opaque base64 |
| Same: symlink policies root, writer file, extra file | Boundaries `policy-symlink-root`, `policy-symlink-writer`, `policy-symlink-extra`: frozen original native mutations, replayed as portable OCI links everywhere and native POSIX symlinks |
| `TestPolicyBindingAbsentAndEmptyNamespace` | Reader `reader-minimal` for absent; `policy-empty-namespace` for empty; `policy-unbound-file` for orphan; shared package `coordinator-workers` for old fixture |
| `TestPolicyBindingDigestPropagationAndStaleAncestors` | `policy-unowned-stale-policy-bytes`, `policy-stale-ancestor`, `policy-repinned-ancestor`; full affected-agent/diff report and OCI artifact-identity comparisons belong to the diff API |
| `TestPolicyBindingUsesOrdinaryNotEffectiveDigest` | Original authored arrays retained above; `policy-effective-digest` refuses framed effective identity as an ordinary document pin. Effective-policy normalization itself is not part of this reader. |

### Policy codec/schema inventory

Sources: [policy tests](../../policy/), [policy binding schema tests](../../internal/artifact/policy_binding_schema_test.go)
and [policy schema tests](../../internal/artifact/policy_schema_test.go).
The existing shared [decode-cases.jsonl](../../policy/testdata/decode-cases.jsonl)
contains 190 wire vectors (27 accepted, 163 refused); all V1/V2 rows, including
refusals, are consumed. Accepted rows alone cannot qualify ordinary policy parity. Consumers must apply the same actual wire bytes, not
only their normalized effective-policy canonical outputs.

| Original Go function/family | Classification and shared coverage |
| --- | --- |
| `policy.TestSharedDecodeCases` | Every row of the existing shared wire corpus; ordinary decode acceptance applies, effective normalization/digest/payload assertions do not |
| `TestSuitePolicyDecodeIsClosed` (all nine bad inputs and trailing-whitespace positive) | Wire relative path, unknown field, duplicate key, unknown version, missing/empty/unknown capability, second value, trailing garbage and JSON-whitespace families |
| `TestPolicyDecodeRejectsUnpairedSurrogate` | Shared unpaired high/low surrogate and UTF-8 refusal families |
| `TestTypedPolicyPathsRequireUTF8` (all five paths) | Wire invalid/truncated UTF-8, encoded surrogate and Unicode/replacement-character families. Resolve/admin/effective/payload calls are separate APIs. |
| `TestNetworkDecodeResolvePayload` | Wire `v2 vector from unsorted duplicates` and reader IPv4 snapshot cover decode; Resolve/canonical/payload outputs are separate APIs |
| `TestNetworkDecodeClosedAndRequired` | Every missing/null/unknown network, endpoint, capability, filesystem/version-mixing family in the wire corpus |
| `TestNetworkIntegralPortLexemes`, `TestNetworkPortsRejectRoundedFractions` | Every existing integral-port and invalid-port lexeme row, with original raw tokens, not floating-point reconstructions |
| `TestNetworkTypedValidation` | Endpoint address/protocol/port, nil network/list, required capability and mixed-profile wire families; malformed UTF-8 belongs to shared JSON. Public Go constant checks and typed Resolve/canonical/payload inputs are not reader APIs. |
| `TestNetworkListLimits` | `policy-count-v2-4096` / `policy-count-v2-4097` freeze raw duplicate endpoint count before normalization; `policy-count-v1-4096` / `policy-count-v1-4097` cover ordinary V1 count. Shared content-retention boundaries cover oversized metadata; original Go oversized suite-decode check retained. Admin/effective/payload limits are separate APIs. |
| `TestNetworkV1WireRemainsClosed` | Wire `v1 with null network`, `v1 with empty network`, `v1 with deny-all network`; legacy administrative decoding is not the reader |
| `TestNetworkSchemaCodecAgreement` | All suite endpoint families (integer forms, string/fractional ports, UDP, CIDR, hostname, unknown/missing field, null) map to the same shared wire rows; admin and effective golden output branches are separate APIs |
| `TestNetworkAddressDiagnosticsDoNotEchoInput` | Shared invalid-address/control refusal families cover acceptance. Exact diagnostic sanitization of the policy Go API remains its own test, not a new public-reader diagnostic contract. |
| `artifact.TestNetworkPolicyV2ReferenceSchema` | All ordinary positive duplicate/empty/port-boundary and negative version/address/protocol/port/required/null/unknown/capability/filesystem families map to shared wire rows; 4097 endpoints → `policy-count-v2-4097` |
| `TestPolicyBindingFixtureConformance` | Shared package `policy-binding`, including its stored OCI/ordinary validation coverage |
| `TestAgentPolicyReferenceSchema` (all nine rows) | v1/v2 positives above; null/empty/null descriptor/missing size/other media/extra field → `policy-ref-*`; traversal is the shared path/owner refusal family, including `policy-unowned-outside-namespace` |
| `TestPolicyBindingRejectsOCIHardlink` | Boundary `policy-hardlink-writer`: original Go archive entries, including earlier regular target `metadata/original.json`; separately accepted regular-file control |
| `TestAdministrativePolicyDecodeIsClosed`, `TestNetworkAdministration`, `TestNetworkAdministrativeV2ReferenceSchema` | Not applicable: administrative policy is supplied to policy resolution, never read from the package |
| `TestCanonicalVectorFilesAgree`, `TestEffectivePolicyUsesUTF16PathOrdering`, `TestCanonicalBytesUseJCSStringEncoding`, `TestCanonicalBytesRejectsOversizedComposition`, `TestCanonicalBytesSizeBoundary`, `TestCompositionCannotWeaken`, `TestNetworkNormalizationDoesNotAlias`, `TestNetworkGoldenVectors` | Not applicable: effective-policy resolution, canonicalization, normalization, aliasing and framed identity are not public package reading |
| `TestPolicyPathLimitsApplyAtEveryBoundary` | Its original admin/Resolve/effective boundaries are not the reader; ordinary suite path count is nevertheless shared by the V1 count snapshots above |
| `TestPayloadPreservesExactBytesAndCapabilities`, `TestNetworkPayloadVersionMismatch`, `TestNetworkPayloadTampering` | Not applicable: provider effective-policy payload verification is not stored authored-policy validation |

### Inventory limits and remaining qualification

All policy/evaluation functions and original row families above are classified;
this is not a claim that all Go APIs have Python counterparts. Shared portable
ordinary semantic snapshots close the additional evaluation and policy-binding
table coverage. Existing shared JSON/type/length/graph/declaration/bundle/OCI/
literal and regex corpora are reused, not replaced.

[reader-boundary-cases.json](reader-boundary-cases.json) closes the five original
integration gaps: oversized policy, three policy symlinks and the policy OCI
hardlink. It stores two accepted complete controls and five refused snapshots,
all produced by the original Go helpers/mutations at the same base. Frozen root
and agent bytes already contain the current pins; neither consumer recomputes
package ancestors. Only the oversized file has null literal bytes, replaced by
one fixed base64-space block repeated 4,194,305 times. Its frozen size and SHA-256
are checked. Links carry explicit type/target, zero ownership and portable modes.
This is a small test-only extension of the entry snapshot, not a mutation DSL.

Python's oversized-policy case first refuses the descriptor's schema maximum
(`schema.maximum` at `/policy/descriptor/size`); Go reaches metadata retention.
The outcomes agree, while the earlier shared metadata-limit tests separately
exercise Python's retained-JSON boundary. Python's first `(code, file, pointer)`
for all 122 refused package/boundary snapshots is frozen in
[reader-diagnostics.json](../../python/tests/reader-diagnostics.json), so an
unrelated earlier refusal cannot silently satisfy a negative test.

`TestSharedReaderBoundaryCases` and Python `test_shared_reader_boundary_cases`
validate the regular controls first, then replay all five refusals through OCI
without extraction. Oversized directory replay runs on every platform; the
three native symlink replays are defined on POSIX only, with no skipped tests.
Windows still exercises all five archived boundaries without requiring native
symlink privileges. The original Go tests remain enabled. All original
policy/evaluation ordinary families now have shared-case or explicit non-reader
classification; this does not claim exhaustive native-race or arbitrary-input
parity. Detached evidence, effective/admin policy, diff reports, execution and
experimental flow are excluded APIs, not silently waived reader cases.

## Go regex syntax cases

[regex-cases.json](regex-cases.json) freezes 702 actual Go 1.26 `regexp.Compile`
accept/refuse results. Go and Python consume the same strings, including Unicode
property aliases, Go-inaccessible script names, capture names, literal/quoted
escapes, zero-count repeat barriers and class-range/POSIX boundaries. Numeric
class endpoints consume a complete hex, braced-hex or octal escape before the
following POSIX atom; invalid classes and accepted controls are shared. The Go
driver checks both `regexp/syntax.Parse` and `regexp.Compile` for every row. They also
include valid patterns at the existing 1,024-byte evaluation bound whose repeated
wide classes exhaust the native binding's matching-program budget without
syntax-only reduction. No expression is matched or executed.

Python checks each class atom before reducing it for structural compilation;
the original authored pattern remains unchanged. The exactly pinned native
library parses the entire expression before attempting its matching program.
Only its exact compile-budget failure status certifies completed parsing; syntax
errors and malformed suffixes still refuse, and unknown budget failures raise.
A small matching-program budget avoids unnecessary wide-class and nullable-range
construction; it is not an input or acceptance limit. Program-size, fresh-process
memory and CPU tests guard those regressions. These cases and bounded generated
Go differentials are evidence, not an exhaustive proof over every possible regex.

## Coverage still held in Go

The existing tests remain enabled. Before another validator claims full ordinary
Go acceptance/refusal parity, share its applicable remaining vectors too:

| Existing coverage | Current source |
| --- | --- |
| Additional runtime-profile wire/diff/evidence cases beyond the shared graph and typed-record tests | [runtime_profile_test.go](../../internal/artifact/runtime_profile_test.go) |
| Evaluation namespace, ownership, ordering, limits and assertion operands | Inventoried below; [reader-semantic-cases.json](reader-semantic-cases.json), existing reader/JSON cases and [regex-cases.json](regex-cases.json) |
| Authored-policy reference/document/namespace failures and stale ancestors | Inventoried below; reader-semantic snapshots and shared [policy wire cases](../../policy/testdata/decode-cases.jsonl); native links remain native tests |
| Additional JSON resource boundaries beyond shared bundle/graph coverage | [validate_test.go](../../internal/artifact/validate_test.go) |
| Inventory presence and declared-mode conflicts | [inventory_presence_test.go](../../internal/artifact/inventory_presence_test.go), [content_identity_test.go](../../internal/artifact/content_identity_test.go) |
| Additional native host access, links/special files and case-fold cases beyond the shared directory vectors | [Unix security](../../internal/artifact/directory_security_unix_test.go), [Windows security](../../internal/artifact/directory_security_windows_test.go), [artifact validation](../../internal/artifact/validate_test.go) |
| Additional inference/execution value cases beyond shared declarations/graphs and direct typed tests | [core inference](../../core/inference_test.go), [artifact execution](../../internal/artifact/execution_test.go) |

Detached evidence, semantic diff report shapes and the separate experimental-flow
opt-in are not a claim of this corpus. Stored evaluation validation never means
that tests or models were executed.

Run the corpus and all existing tests with:

```bash
GOWORK=off go test -count=1 ./...
```
