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
Package identities are owned only by the [shared corpus](conformance/packages.json),
whose paths are relative to its own directory. `rootDigest` is the root document's
JCS digest; `contentDigest` is only the Go semantic-diff compatibility identity,
not a new public format identity. Each `documents` row pins the file's media type, exact canonical
size and SHA-256 digest (raw bytes for Markdown and payload). `schema` selects the
current offline reference schema, or is empty where no Suite document schema applies.
The catalog and custom tool input schema still pass the Go graph loader's checks.

The expectations were independently calculated with Python's SHA-256 over compact,
sorted ASCII JSON with small integers (also JCS for these inputs), and over Go's
ordered test-only content-inventory encoding. Tests read committed vectors; they do
not regenerate them. The payload inventory binds mode 0755; host modes of a loose
directory do not determine portable content identity.

From the repository root, this offline, read-only recipe checks committed bytes
against both vectors. Stored JSON is already canonical (the Go tests enforce it).
Aggregate entries sort by path and emit `path`, `type`, `mode`, `size`, `digest` in
that order, without directories. Modes default to 0644; the payload uses its
provider-declared 0755, never its host mode. This is an identity check, not a writer;
reauthoring content still requires bottom-up descriptor, variant and ancestor updates.

```sh
python3 - <<'PY'
import hashlib, json
from pathlib import Path
root = Path("testdata/rich-evaluations")
sha = lambda data: "sha256:" + hashlib.sha256(data).hexdigest()
docs = {r["path"]: r["descriptor"] for r in json.loads(Path("testdata/rich-evaluations.golden.json").read_bytes())["documents"]}
package = next(r for r in json.loads(Path("testdata/conformance/packages.json").read_bytes()) if r["name"] == root.name)
variant = json.loads((root / "tool-providers/lookup/1.0.0/tool-provider.json").read_bytes())["variants"][0]
modes = {variant["payloadRoot"] + "/" + f["path"]: f["mode"] for f in variant["files"]}
entries = []
for file in sorted(p for p in root.rglob("*") if p.is_file()):
    name = file.relative_to(root).as_posix(); data = file.read_bytes(); digest = sha(data)
    assert (len(data), digest) == (docs[name]["size"], docs[name]["digest"]), name
    entries.append(dict(path=name, type="file", mode=modes.get(name, 0o644), size=len(data), digest=digest))
assert len(entries) == len(docs) == 15
assert sha((root / "agentsuite.json").read_bytes()) == package["rootDigest"]
assert sha(json.dumps(entries, separators=(",", ":")).encode()) == package["contentDigest"]
print("15 documents and root/content identities match")
PY
```
