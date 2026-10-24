# Rich evaluation fixture

[rich-evaluations](rich-evaluations/agentsuite.json) is a directory package for
reader and identity conformance, not a runnable agent or evidence of passing evals.
Its bundled `lookup` payload is inert data, not an MCP server. No tools, models or
judges are executed by the fixture tests.

The writer's index orders cases as `retrieve`, `summarize`, `format`, `offline`,
not filename order. Assertions are ordered constraints, not reference answers:
tool calls, substring requirements/exclusions, a pinned judge with a score threshold,
and a multiline RE2 pattern. Repeat policies cover omitted defaults, explicit runs
with all passes required, and a minimum-pass count. References pin the instruction,
evaluation sources, provider contract, tool input schema and authored policy.

[The golden vector](rich-evaluations.golden.json) stays outside the package tree.
Its `package` row follows the shared corpus's directory-row fields; resolve `path`
relative to this file's directory. `rootDigest` is the root document's JCS digest.
`contentDigest` is only the Go semantic-diff compatibility identity, not a new public
format identity. Each `documents` row pins the file's media type, exact canonical
size and SHA-256 digest (raw bytes for Markdown and payload). `schema` selects the
current offline reference schema, or is empty where no Suite document schema applies.
The catalog and custom tool input schema still pass the Go graph loader's checks.

The expectations were independently calculated with Python's SHA-256 over compact,
sorted ASCII JSON with small integers (also JCS for these inputs), and over Go's
ordered test-only content-inventory encoding. Tests read committed vectors; they do
not regenerate them. The payload inventory binds mode 0755; host modes of a loose
directory do not determine portable content identity.
