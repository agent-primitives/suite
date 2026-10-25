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

## Image references

[image-reference-cases.json](image-reference-cases.json) contains named `imageRef`
strings and Go's expected `valid` results. Go's value validator and both Go and
Python build-profile schema tests consume the same cases for `runtimeBase` and
`harness`. Optional `schemaValid` records a known, pre-existing DNS/path schema
mismatch; otherwise schema acceptance must match `valid`. These recorded gaps
are not exceptions to Go acceptance for a finished package reader.

Bracketed authorities require hexadecimal IPv6 groups: eight full groups or one
`::` replacing at least one group, with 1–4 digits per group in either case.
Optional decimal ports must be 1–65535; leading zeroes are accepted. IPv6 repository
paths are limited to 255 bytes, excluding the authority and digest. Missing/extra/
empty brackets, malformed addresses, dotted tails, zones, invalid ports, trailing
newlines and tag-only references are refused. The schema's `not` guard enforces
that path limit and compensates for differing final-newline anchor behavior in
Go and Python. Existing DNS-authority and path-separator constraints are unchanged;
the vectors explicitly retain their earlier acceptance differences.

Published schema bundles, IDs and canonical-identity algorithms are unchanged;
this draft schema correction belongs to a future minor release, not a patch to a
frozen bundle.

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

[`oci-cases.json`](oci-cases.json) adds 110 named envelope/blob cases, 28 accepted
and 82 refused. `layout` selects one stored layout above; optional `files` maps
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
