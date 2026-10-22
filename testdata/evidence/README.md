# Detached evaluation evidence fixtures

These are synthetic offline conformance fixtures, not records of model execution.
They live outside all suite content roots because embedding results changes the
suite manifest digest.

- `valid.json` is a complete unsigned claim for the local OCI layout assembled
  by `evidenceFixture` in the Go tests from the public evaluation fixture helpers.
  The test validates the schema and verifies the document against that genuine
  layout and independently constructed expected identities. Its manifest digest
  hashes raw OCI manifest bytes; index/case descriptors bind canonical JSON.
- `private-fields.json` adds synthetic privacy canaries in forbidden fields.
  Both the closed schema and verifier must refuse it. Refusal text must not
  disclose the canaries. These strings are not real credentials or endpoints.

Run the fixture checks from the repository root:

```bash
GOWORK=off go test -count=1 -run 'TestEvidence' ./...
```

The tests also mutate identity fields, ordered coverage, repeat thresholds,
execution status, judge scores/configuration, JSON shape and resource bounds.
Failed runs within passing repeat policies remain visible; errors, cancellation,
missing observations, split judging and unknown outcomes cannot qualify.

For consumers, call `evidence.VerifyEvaluation(layoutPath, expected, reader)`.
Resolve `ExpectedEvaluation` from the intended suite/member/composition and
execution/evaluator configuration, not by copying the evidence. Its `Judges`
field is an explicit configuration allowlist, never a wildcard. A successful
`VerifiedEvaluation` contains a validated subject, case/run counts, completion
time and `Unsigned: true`. On `*evidence.EvidenceRefusal`, use `Code` rather
than parse the error text; a UI can show `evaluation: not verified` with that
safe category, and CI should fail closed.

V1 supports exact-model member declarations. Capability-only declarations do
not supply an exact model to match and cannot qualify through a guessed model.
Policy IDs and complete wire/resource/privacy rules are in
[the specification](../../spec.md#824-portable-evaluation-evidence) and
[the closed schema](../../schema/eval-evidence.schema.json). Identifier shape
checks do not detect every possible secret: producers must construct the public
allowlist and hash only documented non-secret configuration projections.

The verifier performs no model, cluster or registry calls. Fixture success proves
consistency of unsigned claims, not who evaluated them, whether observations are
true, trustworthy model identity, or deployment readiness. Signatures and OCI
referrer transport are separate concerns. No fixture should be presented as a
real evaluation pass or used as an authenticity gate.
