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
- [tool-provider-composition.schema.json](../schema/tool-provider-composition.schema.json): standalone provider composition.

## Optional evaluations

- [eval-index.schema.json](../schema/eval-index.schema.json): an agent's ordered evaluation cases.
- [eval-case.schema.json](../schema/eval-case.schema.json): a case and its authored assertions.

## Portable evaluation evidence

- [eval-evidence.schema.json](../schema/eval-evidence.schema.json): external, suite-bound evaluation records.

## Validation and identity

All use JSON Schema 2020-12. The frozen schema identifiers remain
`https://kaimahi.dev/schemas/agentsuite/v1/<file>.schema.json`; downloading a
schema here does not change its identifier. The kaimahi.dev endpoints for schemas
included in v0.1.0 serve those immutable copies, independently of these main-branch
downloads. The new portable evidence schema is a main-branch addition, not part
of v0.1.0; its identifier's hosting is separate from this raw download.

Schemas validate document shapes. The [Go validator](go.md) additionally checks
cross-document references, canonical bytes, descriptors and the closed content graph.

For release-pinned schemas, use the
[v0.1.0 schema directory](https://github.com/agent-primitives/suite/tree/v0.1.0/schema).
