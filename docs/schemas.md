# JSON schemas

Download the current main-branch schemas below. They are copied byte-for-byte
from the repository's schema directory, not rendered as HTML.

- [agent.schema.json](../schema/agent.schema.json)
- [build-profile.schema.json](../schema/build-profile.schema.json)
- [composition.schema.json](../schema/composition.schema.json)
- [eval-case.schema.json](../schema/eval-case.schema.json)
- [eval-index.schema.json](../schema/eval-index.schema.json)
- [suite.schema.json](../schema/suite.schema.json)
- [tool-provider-composition.schema.json](../schema/tool-provider-composition.schema.json)
- [tool-provider.schema.json](../schema/tool-provider.schema.json)

All use JSON Schema 2020-12. The frozen schema identifiers remain
`https://kaimahi.dev/schemas/agentsuite/v1/<file>.schema.json`; downloading a
schema here does not change its identifier. The kaimahi.dev endpoints serve the
immutable v0.1.0 copies, independently of these main-branch downloads.

Schemas validate document shapes. The [Go validator](go.md) additionally checks
cross-document references, canonical bytes, descriptors and the closed content graph.

For release-pinned schemas, use the
[v0.1.0 schema directory](https://github.com/agent-primitives/suite/tree/v0.1.0/schema).
