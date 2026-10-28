# AgentSuite Python package SDK

Read and validate an extracted AgentSuite content directory or a local OCI
image-layout directory. A successful `Package.load` validates the complete
ordinary package graph and retains its exact verified instruction and tool-schema
bytes. It does not execute evaluations, qualify a runtime, enforce policy or
resolve administrative restrictions.

This development distribution is not a PyPI release. Publication and release
qualification are separate maintainer steps. Local writing and canonical identity
helpers are included; registry clients, network fetching and public outer-archive
loading are not.

## Install

From this repository, use CPython 3.10 or newer and require a prebuilt native
RE2 wheel:

```sh
python -m pip install --only-binary=google-re2 ./python
```

The dependency is pinned to `google-re2==1.1.20251105`. Linux, macOS and Windows
are tested on CPython 3.10 and 3.14. A supported interpreter/platform must have a
compatible wheel; do not fall back to a source build or Python `re`. Go is a
conformance-test reference, not a runtime dependency. The native backend checks
stored regex syntax only; it never runs an authored evaluation pattern.

## Read a package

```python
from agent_suite import LoadError, Package

try:
    with Package.load("path/to/package") as package:
        print(package.root_digest)
        print(package.artifact_digest)  # None for an extracted directory
        for agent_id, agent in package.agents.items():
            print(agent_id, agent.source.file)
            for chunk in agent.instructions.content.iter_bytes():
                print(f"{len(chunk)} verified instruction bytes")
            if agent.evaluations is not None:
                for case in agent.evaluations.cases:
                    print(case.declaration.id, case.source.file)
                    for assertion in case.assertions:
                        print(assertion.kind, assertion.source.pointer)
        assert package.validate() == ()
except LoadError as error:
    for diagnostic in error.diagnostics:
        print(diagnostic.source.file, diagnostic.source.pointer, diagnostic.code)
```

Tool schema views have the same byte interface at `provider.tools[i].input_schema.content`
and optional `output_schema.content`, for providers in
`package.tool_providers.values()`. They are literal bodies, not normalized JSON
schemas. `iter_text(errors="strict")` decodes incrementally and can reject
non-UTF-8 content without changing the verified bytes. Byte iteration remains
available for such bodies.

### Authored data and locations

`agents` is a read-only mapping in Suite reference order. `tool_providers` is a
read-only mapping keyed by `(id, version)` in catalog order. Build profiles,
runtime profiles, compositions and provider compositions are ordered tuples of
located `Loaded` records. `package.suite.record` is the frozen Suite declaration;
`package.suite.document.data` is its original JSON.

Agent, provider, tool, policy and evaluation views expose frozen declarations and
source locations. Evaluation cases and assertions retain authored order, all
operands, judge pins, explicit `critical: false`, and optional `runs`/`minPasses`.
No execution defaults or reference-answer extraction are applied. Policy views
retain authored path/endpoint order and duplicates, without effective-policy
normalization.

Normative views carry their original `Document.data` bytes. `Document.value`
decodes a fresh tree; editing that tree cannot alter package identity. Number
lexemes and distinctions between absent, null, empty and false remain available
from that original document rather than a reconstructed model. Where the contract
forbids null or another spelling, loading refuses it instead of normalizing it.
Diagnostics carry a relative file, JSON Pointer and code. The original exception
is retained as the cause of a load error.

### Identity

`root_digest` is SHA-256 over the Suite root document's RFC 8785 JCS bytes, exposed
only after complete validation and literal capture. The root may retain original
noncanonical formatting; pinned normative children must already be canonical.
Instruction and tool-schema pins hash their exact literal bytes.

`artifact_digest` is the distinct SHA-256 of the exact OCI manifest bytes, or
`None` for directory input. It is not the Suite root digest or an aggregate hash
of content. No public aggregate digest or registry-reference API is provided.

The pure `canonical_bytes(value)` and `digest(value)` helpers use RFC 8785, not
sorted Python JSON. `variant_digest(value)` blanks only the top-level
`variantDigest` before canonical hashing. `oci_manifest_digest(manifest_bytes)`
hashes the exact bytes without JSON normalization. These helpers compute identities;
they do not establish that a document or package is valid.

### Lifetime and source independence

After `load` returns, source files and the original OCI layout can be removed.
Literal views and `validate()` use the SDK-owned snapshot, never lazy source
rereads. Capture does not extract an archive tree or promise an atomic filesystem
snapshot against concurrent edits during loading.

One stdlib `SpooledTemporaryFile` uses an aggregate 1 MiB in-memory spill threshold
for captured literals, with bounded 128 KiB transfers and reuse of immutable bytes
already retained as metadata. Larger bodies spill to anonymous/deletion-on-close
temporary storage. The threshold is not an acceptance limit. Memory and backing
storage remain owned until `close()`; storage failures, including disk-full, are
I/O errors.

Prefer a context manager, or explicitly call `close()`. Repeated close is harmless.
Literal views, suspended iterators and `validate()` refuse use after close with
`ValueError`. Frozen normative metadata and identity remain readable; application
copies of returned chunks remain the application's own data.

## Edit and write a package

```python
from agent_suite import Package

with Package.load("path/to/package") as package:
    package.set_instructions("writer", "Answer briefly.\n")
    assert package.validate() == ()
    directory = package.write_directory("path/to/new-content")
    layout = package.write_oci("path/to/new-layout")
    with Package.load(layout) as written:
        assert written.root_digest == package.root_digest
        print(written.artifact_digest)  # Exact new OCI manifest identity
```

`set_instructions(agent_id, str_or_bytes)` is a transactional, copy-on-write edit.
It creates a fresh root-relative instruction file, refreshes the selected agent's
literal descriptor, then its agent manifest and Suite descriptor. Original files
and other agents sharing the original path are not changed. This also avoids
changing provider schemas or executable payloads that happen to share the bytes.
Raw tree mutation is unsupported and stale ancestors are refused, not repaired.
Unrelated authored presence, numeric spellings and raw documents remain intact.

After an edit, reacquire views from the package: earlier frozen metadata remains
historical, but old literal handles become closed. This avoids accumulating old
spools across edits. `root_digest` reflects the validated replacement and
`artifact_digest` becomes `None`; load the written layout for its new OCI identity.
A later edit retires its previous SDK-created instruction file, while original
input files remain untouched. Repeated edits therefore do not accumulate private
instruction-file history. No general manifest builder or payload-editing framework
is exposed.

Both writers return a `Path`. The destination must be absent and its existing
parent must satisfy the native reader's ownership/security checks. Writers do not
overwrite, merge, repair existing permissions or create missing parent directories.
Portable inventory modes and supported content links are retained; an unsupported
native link operation fails with context rather than silently flattening it.
Partial failures do not return success, and cleanup removes only the newly created
output. Runtime source reads use verified pins; output passes full validation.

Writing uses captured metadata and literal bodies where available. To copy an
arbitrary payload that was not retained, keep the original source available and
unchanged until writing completes. Those bytes are rechecked against their loaded
sizes and digests. Source removal still does not affect read-only views or
`validate()`. The writer retains source provenance privately; there is no additional
public source argument or eager whole-package snapshot on ordinary load.

An unedited OCI-to-OCI write verifies and copies its exact existing envelope,
manifest, config and compressed layer bytes. It needs that original layout to
remain available. Edited packages and directory inputs generate a new deterministic
OCI envelope: sorted entries, portable metadata, epoch timestamps and stable gzip
store blocks. Store blocks avoid cross-version compressor heuristics, trading some
space for reproducible bytes. No archive tree is extracted. New OCI bytes need not
match Go's test-only compressor; Go validates the actual emitted package instead.

## Validation boundary

Loading checks the owning offline schemas, canonical pins and media types,
identities, all provider variants and dependency graphs, payload inventories,
portable modes, selected installation collisions, profiles/platforms/harness
links, composition resolutions, inward retention and derived capabilities.
It also closes policy/evaluation namespaces and checks authored policy profiles,
evaluation limits, case/assertion identities, operands, repeats, controls, byte
bounds and Go-compatible RE2 syntax. Validation is not execution or proof that a
policy can be enforced by a particular host.

Directory I/O uses descriptor-relative POSIX opens or stdlib Windows handle/ACL
operations. Host access permissions are separate from portable authored modes.
Windows directory input requires supported owner-only ACLs and refuses descendant
reparse points. Production never repairs ACLs or follows content links. Caller
root aliases follow the Go loader's model. OCI modes and owners come from the
verified layer; OCI handling performs no network requests or archive extraction.

Existing limits remain: 100,000 entries, 4 GiB aggregate regular-file bytes,
256 MiB retained JSON metadata, and 4 MiB per normative JSON document. The JSON
limit does not apply to instruction or tool-schema literal bodies. Both wheel
paths carry the exact repository schema bytes, IDs, source revision and SHA-256
inventory. Runtime schema resolution is closed and never downloads resources.

## Development checks

From the repository root, with the repository's Go toolchain installed:

```sh
python -m pip install --only-binary=google-re2 -r python/requirements-dev.txt ./python
python -m pytest python/tests -q
python -m mypy --config-file python/pyproject.toml python/src/agent_suite
```

Run packaging suites sequentially: setuptools staging is shared. Tests require
named passes with no skips, replay shared Go/Python conformance inputs, exercise
native regex dialect differences, and install direct and sdist-derived wheels in
an isolated environment with no runtime checkout dependency.
