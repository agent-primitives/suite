# Review guidance for AgentSuite

[CONTRIBUTING.md](../CONTRIBUTING.md) and [spec.md](../spec.md) are the rules.
Adapted from the source Kaimahi review guidance. Review in this order:

1. **Fail closed.** Missing, unreadable, partial or ambiguous content must refuse,
   never become success, a default or a silent skip. Preserve bounded offline
   validation, strict decoding, path safety and complete graph closure.
2. **Evidence and identity.** Preserve schema IDs, media types, canonical JSON,
   descriptors and digest semantics. Validate optional evaluation storage and
   identity without claiming execution, runtime safety or a passing evaluation.
3. **Credentials and privacy.** No secrets, tokens, private endpoints or user
   payloads in fixtures, logs, errors or published suite content.
4. **Ownership.** This is the portable format/model/validation/diff library,
   not a builder, registry client, runtime or governance platform. Keep the Go
   package agentsuite and the module github.com/agent-primitives/suite.
5. **Scope and size.** One change per PR; flag unrelated edits, timeout increases
   used to hide failures, generated-file hand edits, and tests that add no distinct
   behavioral coverage.
6. **Docs and compatibility.** Public contract changes update docs and release
   notes. Breaking Go, validation, wire, digest or semantic-diff behavior requires
   a documented v0 minor release and migration guidance.
7. **Verification.** Require conformance fixture passes without skips, race tests,
   vet, staticcheck, gofmt and documentation checks. No committed local replaces
   or workspace files.

Skip style nits already enforced by tools. Prefer one concrete failing scenario
over speculative comments. Repository controls and maintainer-team approval are
operator decisions; do not infer them from policy files.
