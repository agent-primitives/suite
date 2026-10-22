# Policy contract

This package owns AgentSuite policy meaning: strict intent validation,
non-weakening administrative composition, exact canonical effective bytes and
a domain-separated digest. Consumers preserve the bytes rather than
reserializing them. The normative contract is
[specification Section 5.2](../spec.md#appendix-b-standalone-policy-contracts-normative).

## Versions

`agentsuite.policy/v1` remains filesystem-only, with the unchanged
`filesystem/deny-write/v1` capability. Its path sets use unsigned UTF-16
code-unit ordering so Go and RFC 8785/JavaScript implementations produce the
same canonical bytes. It requires denial of create, writable open/write,
truncate, rename effects, unlink, link, metadata and symlink mutation,
including declared mount/path bypass coverage. A provider must reject when it
cannot cover the full required operation set.

`agentsuite.policy/v2` is the explicit **network-only** successor:

```json
{
  "version": "agentsuite.policy/v2",
  "network": {
    "egressAllow": [
      {"address": "192.0.2.10", "protocol": "TCP", "port": 443}
    ]
  },
  "requiredCapabilities": ["network/egress-allow/v1"]
}
```

Only literal canonical IPv4, exact TCP and explicit integer ports 1–65535 are
supported. Hostnames, CIDR (including `/32`), UDP, IPv6, ranges and unknown fields
refuse, never get ignored. There are no implicit DNS, model, controller or other
allowances: the model endpoint is listed like anything else. `egressAllow: []`
is deny-all; missing/null is invalid. Duplicate tuples collapse and sort by
lexicographic address, then numeric port.

## Administrative restrictions and API

`DecodeSuitePolicy`, `Validate`, `Resolve`, `CanonicalBytes`, `Payload` and
`VerifyPayload` support both versions. `SchemaVersion` deliberately stays v1;
use `SchemaVersionV2` to opt into v2, with exactly `NetworkEgressAllow` required.
Neither version silently converts to the other or accepts the other's fields.
`VerifyPayload` validates policy identity, not a provider's ability to enforce it;
a filesystem-only provider must still refuse v2/network requirements.

Legacy `DecodeAdministrativePolicy` remains v1-only. Use
`DecodeAdministrativePolicyForVersion(data, suite.Version)` for explicit version
selection. For v1, omitted `denyWritePaths` and an explicit empty array add no
restriction; explicit `null` refuses rather than becoming an absent overlay.
V2 admin `{}` adds no restriction; supplying
`{"network":{"egressAllow":[]}}` denies all. A supplied tuple set intersects the
suite's tuple set, never unions or grants extra endpoints. Restrictions from the
other profile refuse rather than being dropped. Lists are bounded at 4096
entries before deduplication; canonical output retains the v1 4 MiB limit.

The `oci` package validates optional [Agent policy bindings](../spec.md#83-agent-policy-binding)
at `policies/<agent-id>.json` in extracted and OCI content. These descriptors
commit exact authored JCS bytes with ordinary content SHA-256, not this package's
framed effective-policy digest. Authored array order/duplicates remain byte-bound;
`Resolve` and `CanonicalBytes` separately normalize effective policy sets. No
administrative deployment restrictions are implicitly folded into the artifact.

Valid bytes and graph references do not prove installation, observed activation,
startup safety or enforcement. A provider must refuse if it cannot mediate the
claimed boundary; no target is qualified by this package.

## Language-neutral vectors

`testdata/effective-policy-v1.json` and its `.sha256` preserve the original v1
vector. `testdata/effective-policy-ordering-v1.json` distinguishes unsigned
UTF-16 ordering from Go code-point ordering. `testdata/effective-policy-v2.json` and
`testdata/effective-policy-v2-deny-all.json`, each with a `.sha256` companion,
cover the v2 nonempty and deny-all cases. Read the JSON file bytes directly,
without adding a newline or parsing/reserializing them before digest verification.

`testdata/decode-cases.jsonl` holds one canonical JSON case per line: a `name`, an
`input` (or `inputHex` for byte-level input such as a BOM or malformed UTF-8),
whether `DecodeSuitePolicy` accepts it, and for accepted cases the canonical
bytes and digest. Both the Go and TypeScript tests run every case in this corpus.
The format needs no Go, so another implementation can
run the same refusal, canonical-bytes and digest expectations; add new
wire-format edge cases there.

Both versions use the **unchanged** `agentsuite-effective-policy\0v1\0` domain,
uint64 big-endian byte-length framing and SHA-256. Here `v1` identifies the digest
framing; the bytes already commit to the policy version. Do not substitute the
`core.Digest` content digest function. Payload outer/inner versions and capabilities
must match, and the policy bytes must be exactly canonical, not merely have a
matching digest.

## TypeScript implementation

The small [TypeScript policy package](typescript/README.md) implements strict
v1/v2 wire decoding, canonicalization, framed digests and payload verification
without runtime dependencies. Its tests read these same shared vectors and
compare bounded malformed/boundary inputs directly with Go. It does not provide
administrative composition, enforcement or a new policy schema.
