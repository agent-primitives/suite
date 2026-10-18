# TypeScript policy identity

Small, dependency-free runtime implementation of the [policy contract](../README.md)
([normative Appendix B](../../spec.md#appendix-b-standalone-policy-contracts-normative)).
It handles filesystem v1 and network-only v2, not policy enforcement or
administrative composition. Go and the shared `policy/testdata` remain the
behavior and fixture authority. No Go source, schema or expected vector changes
are needed.

## Location and runtime

The private, unpublished ESM package lives alongside the Go policy implementation
at `policy/typescript`. The package name is a local placeholder, not a registry
reservation or a publishing plan. There are **no runtime dependencies**, Node
imports or Go subprocesses in `src`. TypeScript and Playwright are development
only. `npm run build` produces native ES2022 modules and declarations in `dist`;
serve those modules as-is or import the entry module into a consumer's bundler.
There is no generated bundle, CommonJS entry or Node polyfill layer.

Runtime baseline: Node.js 22 or a modern browser with native ES2022,
`TextEncoder`, fatal UTF-8 `TextDecoder`, `DataView.setBigUint64` and Web Crypto
SHA-256. Browser hashing needs a secure context (HTTPS or loopback). The browser
check executes the emitted ESM, shared vectors, digest/payload operations and
explicit refusal/boundary cases in real Chromium, not a DOM shim. This does not
qualify Firefox, Safari, older engines, a particular dashboard or a provider's
enforcement boundary. Chromium was independently tested; this opt-in check is
not run by the TypeScript CI job.

## API

```ts
import {
  canonicalize, decodePolicy, digest, payload, verifyPayload,
} from './dist/index.js';

const authoredBytes = new TextEncoder().encode(JSON.stringify({
  version: 'agentsuite.policy/v2',
  network: { egressAllow: [{ address: '192.0.2.10', protocol: 'TCP', port: 443 }] },
  requiredCapabilities: ['network/egress-allow/v1'],
}));
const decoded = decodePolicy(authoredBytes); // validated discriminated Policy union
const canonicalBytes = canonicalize(authoredBytes); // fresh Uint8Array
const identity = await digest(canonicalBytes); // sha256:lowercase-hex
const envelope = await payload(authoredBytes); // canonical bytes plus identity
await verifyPayload(envelope); // resolves void, throws on refusal
```

- `decodePolicy(bytes)` validates exactly one wire object and returns fresh data.
  It preserves authored array order/duplicates, but exposes accepted numeric port
  spellings as integers. It does not claim the original bytes were canonical.
- `canonicalize(bytes)` validates, deduplicates and sorts the appropriate rule
  set, returning canonical UTF-8 bytes. Use raw received bytes, **not** a prior
  `JSON.parse`/`JSON.stringify` round trip: duplicate keys and fraction lexemes
  would already be lost.
- `digest(bytes)` applies the unchanged policy domain
  `agentsuite-effective-policy\0v1\0`, uint64 big-endian length and SHA-256.
  Like Go's `Digest`, it hashes arbitrary bytes and does **not** validate policy.
- `payload(bytes)` canonicalizes validated input and returns a `ProviderPayload`
  with `version`, `policyBytes: Uint8Array`, `policyDigest` and
  `requiredCapabilities`. Input and returned arrays do not alias.
- `verifyPayload(envelope)` checks supported version, exact profile capabilities,
  digest, strict inner decoding, outer/inner version agreement and byte-for-byte
  canonicality. A self-consistent digest over noncanonical bytes still refuses.
  Bytes and scalar identity fields are snapshotted before asynchronous hashing;
  successful verification refers to that snapshot, not subsequent caller writes.

`Policy`, `Endpoint` and `ProviderPayload` types and the four version/capability
constants are exported. All validation failures throw `Error` (including native
JSON/UTF-8 errors); message wording is not a stable API or a Go diagnostic clone.
Messages do not interpolate policy paths or endpoint addresses.

The envelope API corresponds to Go's typed `ProviderPayload`, not a JSON carrier
decoder. There is deliberately no base64 transport/parser API, signature scheme,
provider capability negotiation or administrative-policy resolver. An application
must decode its carrier into bytes without changing those bytes. Verification
proves policy identity only, never authorization or enforcement.

## Strictness and implementation size

The small internal reader exists only because `JSON.parse` discards duplicate
keys and exact numbers. It bounds wire input to 4 MiB, nesting to 100 containers,
each object to 1024 members and the document to 100,000 members, matching Go's
codec. It rejects invalid UTF-8, BOM outside strings, unpaired surrogates,
non-JSON whitespace, invalid escapes, duplicate decoded names and trailing data.
`JSON.parse` is used only for a delimited string token, never a whole document.
Closed policy shapes then check exact field spelling and types (including null
and missing distinctions) and list bounds of 4096 before normalization.

Ports accept integral decimal/exponent spellings such as `443.0` and `4.43e2`,
but reject fractions even when IEEE-754 rounds them to an integer. Decimal digit
checks avoid expanding huge powers or allocating huge arbitrary-precision
rationals; they also preserve Go `big.Rat`'s adjusted decimal exponent bound.
No generic JSON canonicalizer is exposed: the closed schema has fixed keys,
validated bounded integers and Unicode strings. Explicit key construction plus
ECMAScript string serialization emits JCS for this schema. V1 set sorting uses
JavaScript's unsigned UTF-16 default ordering, **not** `localeCompare` or Unicode
code-point ordering; v2 sorts address strings lexicographically then port
numerically. No filesystem or DNS APIs are involved.

### Known Go numeric-spelling difference

All shared canonical vectors match exactly, but universal raw-input
acceptance/refusal parity is not claimed. With Go 1.26.0, a port token formed
as `'1' + '0'.repeat(800) + 'e-800'` is rejected by the reference decoder even
though it is exactly integer 1: its floating-point range precheck reads 0.1.
This is consistent with [golang/go#42436](https://github.com/golang/go/issues/42436).
TypeScript retains the exact value and emits canonical `"port":1`, and Go
successfully verifies the resulting canonical payload. This is not an observed
canonical-byte/digest mismatch or demonstrated enforcement bypass.

A focused regression checks the exact port-1 result, canonical bytes/digest
against Go, payload verification in both implementations, and refusal of a
nearby true fraction that IEEE-754 rounds to 1. Go's decision on the original
long spelling is diagnostic: if a future toolchain accepts it, canonical
identity must still match. The test does not require Go's bug to persist.
No Go correction or emulation of that runtime bug is included.

## Build and tests

From the repository root, with Node.js 22 and Go as required by `go.mod`:

```sh
npm --prefix policy/typescript ci --ignore-scripts
npm --prefix policy/typescript test
```

Optional browser verification requires an explicit Chromium installation and
invocation; neither `npm test` nor the TypeScript CI job performs these steps:

```sh
npm --prefix policy/typescript exec playwright install --with-deps chromium
npm --prefix policy/typescript run test:browser
```

`npm test` first compiles with strict typechecking, then runs Node's test runner.
`decode-cases.test.mjs` runs every case in `policy/testdata/decode-cases.jsonl`.
Every `.json` in the shared `policy/testdata` directory is discovered and its
companion `.sha256` is required. Expected bytes/digests are never copied into TS
fixtures. A bounded deterministic suite compares accept/refuse, canonical bytes,
digests and verification with the **actual Go package**, using a test-only Go
oracle with a line protocol. The current oracle is compiled once when first
needed in a test-file run; each differential test gets its own process.
The suite removes its temporary build directory after the tests finish.
The oracle is excluded from ordinary `go test ./...` package discovery; its
subprocesses are never part of production code. Missing Go or Chromium fails
the respective test, not a silent skip.

Explicit tests include duplicate/escaped keys; unknown/case-mismatched fields;
missing/null/empty and cross-version fields; numeric spelling, rounding,
overflow and port bounds; IP syntax; controls/escaping and UTF-16 ordering;
invalid UTF-8 and surrogate pairs; trailing data; byte/list/nesting/member
limits; malformed payload identities and correctly digested noncanonical bytes.
Seeded valid documents, exact decimal/exponent variations and byte mutations
exercise both profiles. Differential testing is bounded regression evidence,
not an exhaustive proof over all inputs. CI runs strict compilation and the Node
and Go differential tests in an additional job, without installing or running
Chromium. The existing native Go and documentation checks, including the
documentation browser tests, remain unchanged.
