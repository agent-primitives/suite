# Policy contract

This package owns AgentSuite policy meaning: strict intent validation,
non-weakening administrative composition, exact canonical effective bytes and
a domain-separated digest. Consumers preserve the bytes rather than
reserializing them. The normative contract is
[specification Appendix B](../spec.md#appendix-b-standalone-policy-contracts-normative).

## Versions

`agentsuite.policy/v1` remains filesystem-only, with the unchanged
`filesystem/deny-write/v1` capability and canonical vectors. It requires denial
of create, writable open/write, truncate, rename effects, unlink, link, metadata
and symlink mutation, including declared mount/path bypass coverage. A provider
must reject when it cannot cover the full required operation set.

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
selection. V2 admin `{}` adds no restriction; supplying
`{"network":{"egressAllow":[]}}` denies all. A supplied tuple set intersects the
suite's tuple set, never unions or grants extra endpoints. Restrictions from the
other profile refuse rather than being dropped. Lists are bounded at 4096
entries before deduplication; canonical output retains the v1 4 MiB limit.

This is a standalone contract: no Agent descriptor, OCI graph edge or runtime
integration is added. Valid bytes do not prove installation, observed activation,
startup safety or enforcement. A provider must refuse if it cannot mediate the
claimed boundary; no target is qualified by this package.

## Language-neutral vectors

`testdata/effective-policy-v1.json` and its `.sha256` preserve the original v1
vector. `testdata/effective-policy-v2.json` and
`testdata/effective-policy-v2-deny-all.json`, each with a `.sha256` companion,
cover the v2 nonempty and deny-all cases. Read the JSON file bytes directly,
without adding a newline or parsing/reserializing them before digest verification.

Both versions use the **unchanged** `agentsuite-effective-policy\0v1\0` domain,
uint64 big-endian byte-length framing and SHA-256. Here `v1` identifies the digest
framing; the bytes already commit to the policy version. Do not substitute the
root artifact digest function. Payload outer/inner versions and capabilities
must match, and the policy bytes must be exactly canonical, not merely have a
matching digest.
