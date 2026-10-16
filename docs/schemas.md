# JSON schemas

Download the current main-branch schemas below. They are copied byte-for-byte
from the repository's schema directory, not rendered as HTML.

- [agent.schema.json](../schema/agent.schema.json)
- [build-profile.schema.json](../schema/build-profile.schema.json)
- [composition.schema.json](../schema/composition.schema.json)
- [eval-case.schema.json](../schema/eval-case.schema.json)
- [eval-index.schema.json](../schema/eval-index.schema.json)
- [execution.schema.json](../schema/execution.schema.json) (experimental)
- [inference.schema.json](../schema/inference.schema.json) (experimental)
- [suite.schema.json](../schema/suite.schema.json)
- [tool-provider-composition.schema.json](../schema/tool-provider-composition.schema.json)
- [tool-provider.schema.json](../schema/tool-provider.schema.json)

All use JSON Schema 2020-12. The frozen schema identifiers remain
`https://kaimahi.dev/schemas/agentsuite/v1/<file>.schema.json`; downloading a
schema here does not change its identifier. The original eight schemas have
immutable v0.1.0 copies at the kaimahi.dev endpoints, independently of these
main-branch downloads. The experimental execution and inference schemas are
main-branch additions, not part of v0.1.0.

Schemas validate document shapes. The [Go validator](go.md) additionally checks
cross-document references, canonical bytes, descriptors and the closed content graph.

For release-pinned schemas, use the
[v0.1.0 schema directory](https://github.com/agent-primitives/suite/tree/v0.1.0/schema).
