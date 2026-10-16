# JSON schemas

Download the current main-branch schemas below. They are copied byte-for-byte
from the repository's schema directory, not rendered as HTML.

## Suite entry point

- [suite.schema.json](../schema/suite.schema.json): root manifest and its content references.

## Agents and sandbox inputs

- [agent.schema.json](../schema/agent.schema.json): agent instructions and tool requirements.
- [tool-provider.schema.json](../schema/tool-provider.schema.json): provider contracts and variants.
- [composition.schema.json](../schema/composition.schema.json): agent and provider selections.
- [build-profile.schema.json](../schema/build-profile.schema.json): sandbox build inputs.
- [runtime-profile.schema.json](../schema/runtime-profile.schema.json): optional pinned runtime/harness/renderer requirements and configuration ABI.
- [tool-provider-composition.schema.json](../schema/tool-provider-composition.schema.json): standalone provider composition.

## Optional evaluations

- [eval-index.schema.json](../schema/eval-index.schema.json): an agent's ordered evaluation cases.
- [eval-case.schema.json](../schema/eval-case.schema.json): a case and its authored assertions.

## Portable evaluation evidence

- [eval-evidence.schema.json](../schema/eval-evidence.schema.json): external, suite-bound evaluation records.

## Experimental execution and inference contracts

- [execution.schema.json](../schema/execution.schema.json): a built image's execution interface (experimental).
- [inference.schema.json](../schema/inference.schema.json): inference requirements (experimental).

## Standalone network-only policies

- [policy-v2.schema.json](../schema/policy-v2.schema.json): authored/effective IPv4 TCP egress allowances.
- [administrative-policy-v2.schema.json](../schema/administrative-policy-v2.schema.json): optional intersecting restrictions.

The Agent schema also defines optional policy FileRefs; the validator checks
owning-Agent paths, descriptor/version agreement and closed policy graph membership.
See [Agent policy binding](../spec.md#83-agent-policy-binding).
See the [normative policy contract](../spec.md#appendix-b-standalone-policy-contracts-normative).

## Validation and identity

All use JSON Schema 2020-12. Existing artifact schema identifiers remain
`https://kaimahi.dev/schemas/agentsuite/v1/<file>.schema.json`; downloading a
schema here does not change its identifier. The standalone policy v2 additions
use `https://kaimahi.dev/schemas/agentsuite/policy/v2/` identifiers; they do not
rename any existing schema. The kaimahi.dev endpoints for schemas
included in v0.1.0 serve those immutable copies, independently of these main-branch
downloads. The portable evidence schema and the experimental execution and
inference schemas are main-branch additions, not part of v0.1.0; their
identifiers' hosting is separate from these raw downloads. Hosting of the new
policy identifiers is likewise separate from the raw downloads.

Schemas validate document shapes. The [Go validator](go.md) additionally checks
cross-document references, canonical bytes, descriptors and the closed content graph.
Policy semantics and payload verification use the `policy` package. `ValidatePath`
reuses its semantic decoder for explicitly bound authored policy files; unreferenced
files in the policy namespace refuse rather than being silently discovered or applied.

For release-pinned schemas, use the
[v0.1.0 schema directory](https://github.com/agent-primitives/suite/tree/v0.1.0/schema).
