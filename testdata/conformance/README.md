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

## Coverage still held in Go

The existing tests remain enabled. Before another validator claims full ordinary
Go acceptance/refusal parity, share its applicable remaining vectors too:

| Existing coverage | Current source |
| --- | --- |
| Runtime-profile graphs, selector/ref/presence failures | [runtime_profile_test.go](../../internal/artifact/runtime_profile_test.go) |
| Evaluation namespace, ownership, ordering, limits, assertion operands and Go regex syntax | [evaluation_test.go](../../internal/artifact/evaluation_test.go) |
| Authored-policy reference/document/namespace failures and stale ancestors | [policy_binding_test.go](../../internal/artifact/policy_binding_test.go) |
| Bundle closure, install collisions, variant refusals and additional JSON resource boundaries | [validate_test.go](../../internal/artifact/validate_test.go) |
| Inventory presence and declared-mode conflicts | [inventory_presence_test.go](../../internal/artifact/inventory_presence_test.go), [content_identity_test.go](../../internal/artifact/content_identity_test.go) |
| Additional native host access, links/special files and case-fold cases beyond the shared directory vectors | [Unix security](../../internal/artifact/directory_security_unix_test.go), [Windows security](../../internal/artifact/directory_security_windows_test.go), [artifact validation](../../internal/artifact/validate_test.go) |
| Experimental inference/execution value-level checks included by ordinary validation | [core inference](../../core/inference_test.go), [artifact execution](../../internal/artifact/execution_test.go) |

Detached evidence, semantic diff report shapes and the separate experimental-flow
opt-in are not a claim of this corpus. Stored evaluation validation never means
that tests or models were executed.

Run the corpus and all existing tests with:

```bash
GOWORK=off go test -count=1 ./...
```
