# Judge producer profile (main, not yet released)

The optional `github.com/agent-primitives/suite/judge` package produces judge
requests and verifies raw responses. It is new on main, **not in v0.7.0**.
Consumers must wait for a published root module release containing this API;
there is no separate judge module or tag. No consumer integration is claimed.

This companion producer contract does not change the [storage specification](../spec.md),
public evidence v1, schemas, historical evaluator identities or reader acceptance.
Storage remains prompt-agnostic. This profile is one explicit choice of producer,
not a requirement that every Suite evaluator use this prompt.

## Authority and content admission

Suite owns the pure policy, byte projection, response decoder and score quorum.
Trusted runtimes own routes, credentials, content admission, budgets, dispatch,
retention, original journals and safe diagnostics. This package has no network,
filesystem, credential or callback API.

Before retention, the trusted runtime must apply its content-admission policy,
including credential-echo rejection and other applicable secret checks. Admission
failure makes that run unknown; it must not become redaction-only or a passing
score. Apply equivalent acceptance rules for equivalent sensitive context across
Publish and Deploy. This package does not scan for secrets: a response containing
credential-shaped text can be syntactically valid to the pure decoder while still
being unacceptable to the runtime. Never pass credentials into this API, profile
hashes, configuration hashes or stored evidence. Raw data and returned reasoning
must not be logged or displayed without the runtime's admission/rendering checks.

A successful `Verify` recomputes scores; it does not authenticate response origins,
prove distinct executions, attest a model version, or authorize qualification.
The host must independently anchor each original request/response to the verified
package, accepted configuration, attributed answer and distinct run/call slots.
A package or a client-supplied passing flag cannot supply that authority. Identical
valid response bytes can come from independent calls; byte inequality is not a
substitute for execution ownership.

## Public API

```go
import "github.com/agent-primitives/suite/judge"

definition := judge.Definition{
    Model: "judge", Version: "v1", Rubric: "Be correct.", MinScore: 80,
}
request, err := judge.Prepare(definition, "question", "answer")
// The runtime admits content, executes two bounded calls, and retains originals.
// This example performs no calls.
_ = request
_ = err
```

- `Prepare(d, input, answer)` returns owned exact request bytes, not a transport.
- `DecodeResponse(d, raw)` returns a `Sample` with `Score`, `ObservedModel`,
  `ModelMatch` (`requested` or `version-qualified`) and original `Reasoning`.
  Reasoning is transient, untrusted diagnostic content, never portable evidence.
- `Verify(d, input, answer, request, responses)` reconstructs and byte-compares the
  request and validates exactly two original response envelopes. It returns a
  payload-free `Result{Outcome, Scores, ObservedModels}`. It accepts no score claim.
- `Profile()` returns `core.EvidenceImplementation{ID, Version, Digest}` for this
  producer. It is **not** an evidence policy.
- `ConfigurationDigest(d)` returns the route-free public configuration identity.
- `ExecutionConfigurationDigest(d, routeDigest)` additionally binds a trusted,
  non-secret route/configuration digest. Its result is private execution identity.

`ErrDefinition`, `ErrRequest`, `ErrResponse` and `ErrSamples` contain no operand or
provider text. Any `Verify` error returns `Outcome: "unknown"` with no scores or
observed models. A valid split returns unknown with both scores/models and no
error. `DecodeResponse` errors return a zero Sample, not partial diagnostics.
Callers must check errors and the outcome, not just error absence.

## Version 1 producer contract

The producer ID is `agentsuite-judge-producer-v1`, version `1.0.0`.
Its digest is SHA-256 of the JCS-canonical
[profile-contract.json](../testdata/judge-producer-v1/profile-contract.json).
That manifest binds the exact system policy and the projection, decoder and
aggregation semantic implementation identities. These are contract identities,
not Go source/binary hashes or provider attestation. Non-equivalent policy,
projection, validation or quorum changes need a new producer identity/version;
never relabel historical evidence with this profile.

### Operands and request bytes

`Model` and `Version` are authored declarations: nonblank printable ASCII, each
at most 256 bytes, preserved byte-for-byte. `Rubric` is nonblank valid UTF-8, at
most 4096 bytes, with no control characters except newline/tab. `MinScore` is
inclusive in 0..100. No model or version is inferred, normalized or defaulted.

`Prepare` uses Go JSON string escaping and the exact member order shown by
[request.json](../testdata/judge-producer-v1/request.json), with no trailing newline:

1. `model`: authored model, never the substituted candidate model.
2. `max_completion_tokens`: 1024.
3. `stream`: explicit false. No temperature, tools or sampling override.
4. `messages`: system policy first, then one user message. The user content is a
   JSON object ordered `input`, `answer`, `rubric`; all three are untrusted data.

Input and answer must be valid UTF-8. Each input and the complete encoded request
are bounded by one MiB, including double escaping. Runtime input/context/request
limits can be stricter and must be checked after the candidate answer exists.
Never truncate an answer or rewrite the body to fit. A runtime that re-encodes
fields, omits `stream:false` or changes 1024 cannot claim these exact sent bytes.

### Original response decoding

The complete original Chat envelope is bounded to 64 KiB. JSON must be one valid
UTF-8 document with unique keys at every depth and paired Unicode escapes.
Unknown provider envelope/choice/message metadata is allowed and follows the
shared JSON codec's numeric acceptance; this profile does not promise lossless
numeric metadata conversion or interpret that metadata as score evidence.
Required fields are exact-case and cannot be absent or null. Score parsing below
is separately integer-only; the decoder does not replace the original response
bytes with canonical JSON.

There must be exactly one choice, `finish_reason: "stop"`, an assistant message
and string content. Message `tool_calls`, `function_call` and `refusal`, including
case-folded aliases recognized by runtime adapters, must be absent or null
(even an empty array/string is a refusal). The envelope model must
exactly equal `Model` or `Model + "-" + Version`; labels are declarations, not
attestation. No prefix, whitespace normalization or case folding is used.

Content must be one closed JSON object with exactly `score` and `reasoning`.
`score` is an integer 0..100, not a string, float or null. `reasoning` is a valid
UTF-8 string of at most 4096 bytes, not null. Duplicate/unknown fields, malformed
Unicode, trailing values, missing data and unavailable responses cannot pass.
The decoder does not normalize or sanitize reasoning for display.

### Quorum and failure

A known verdict needs two valid independently executed samples for the same
attributed answer, with no inference retries. Reserve both slots before dispatch.
Stop further sends after a mechanical/unavailable/invalid sample; discard all
partial claim scores/models. Dispatch and early stopping are runtime obligations,
not actions performed by this pure package.

Both scores at or above `MinScore` pass. Both below fail. A valid split is unknown
and retains both scores/models. Unknown must veto repeat-policy qualification;
`minPasses` cannot convert it to pass. A known fail does not authorize truncating
other required inventory. Changing this execution wording does not reinterpret
historical kmx evaluator fingerprints or the public evidence policy.

## Configuration and portable evidence

All hashes use lowercase `sha256:` spelling. The public configuration digest is
SHA-256 of a JCS projection with domain `agentsuite.judge.configuration/v1`,
producer identity, authored model/version, raw rubric-byte digest, threshold,
two samples, 1024 tokens, stream=false and `sampling: "no-override"`.
The private execution digest uses domain `agentsuite.judge.execution/v1`, the
public configuration digest and an accepted route digest. That route input must
already be a lowercase SHA-256 digest and contain no credential-derived material.
The helper checks its spelling; it cannot establish its provenance.

For public `EvidenceJudgeConfiguration`, retain `Policy.ID` =
`agentsuite-double-score-v1` and its existing version; put the new **public**
configuration digest in `Policy.ConfigurationDigest`. Do not put the producer ID
in `Policy.ID`, and do not export the private route digest or any raw content.
Each distinct rubric/threshold may require a separate accepted configuration;
build the full independently expected set from the verified inventory and
deduplicate equal entries, within the existing evidence bounds.

Publish and Deploy independently reconstruct public expectations from the
verified package and accepted producer. Each separately reconstructs private
execution expectations from its frozen host configuration. The producer policy
and authored judge pins are the same; endpoint/configuration digests may differ.
No caller may derive accepted expectations from an uploaded score claim.

The [storage verifier](go.md#optional-runtime-profiles) checks claim consistency
against independent expectations. It cannot authenticate raw requests or scores.
A self-consistent forged passing claim can pass storage checking while original
responses recompute to fail; hosts must perform trusted original-byte verification.

## Conformance and compatibility

The [producer fixtures](../testdata/judge-producer-v1/definition.json) include exact
request, canonical profile contract, producer/public/private identity and original
passing/below-threshold envelopes. Tests cover prompt-data separation, operand and
route binding, malformed envelopes/content, bounds, quorum, request substitution
and the unchanged portable claim verifier. They execute no models and qualify no
provider. Existing schemas and conformance fixtures are unchanged.
