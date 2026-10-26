# AgentSuite Python implementation

Internal format foundation under development. There is no public package reader,
writer, registry transport or executable API yet. Do not upload this development
distribution to PyPI.

Private modules provide strict JSON decoding, RFC 8785 canonicalization, explicit
literal-byte hashes, raw-preserving common records and offline schema-only
diagnostics. Schema checks alone do not validate a package's graph or qualify a
runtime. Construction checks the owning bundle's references in supported schema
locations, including optional branches. Unresolved references reached during validation
are refused. Diagnostics retain pointers and codes without copying instance values.
The finished public reader and full graph validation remain later work.

Private directory I/O now builds content records through descriptor-relative
POSIX opens or stdlib Windows handle/ACL operations. It preserves raw bytes and
portable modes, checks paths and Go-compatible case collisions, and hashes files
by bounded streaming. Only `.json` files up to 4 MiB are retained; aggregate limits
are 100,000 entries, 4 GiB of regular-file bytes and 256 MiB of retained metadata.
Host access permissions are checked separately from portable content modes.
Windows input requires supported owner-only ACLs and refuses descendant reparse
points. Production never repairs input permissions or follows content links.
Root aliases and opened-directory capabilities follow the Go loader's model;
this does not promise an atomic snapshot against concurrent same-size writes.
Loading these private records does not verify a package graph or package identity.

Private gzip/tar layer loading preserves archived modes, owners, links and
streamed file hashes, including PAX/GNU names and sparse logical content. It
matches the Go reader's gzip members, checksums, timestamps and tar framing
without extracting files or following links. The same content and retained-JSON
limits apply. A successful layer read is not schema, graph or package-identity
validation.

Private OCI layout loading now verifies closed envelopes, local blob digests and
sizes, embedded-data agreement, exact empty config bytes and one content layer.
It accepts OCI layout directories containing gzip/tar layers, not outer archive
files. OCI file checks refuse final-component links and special files without
applying loose-content ownership/ACL policy. Caller-selected root aliases are
allowed. Path-based blob-directory checks and hash-then-parse reads match Go;
they do not provide an immutable snapshot against concurrent changes.
The returned artifact digest hashes literal OCI manifest bytes, not the Suite
root document or a verified package graph. No network or extraction is involved.

Private document collection now preserves original JSON bytes alongside frozen,
source-addressable Suite, Agent, catalog, ToolProvider and nested declaration
records. Pinned manifests must already be canonical and match their media type,
size and SHA-256; the root manifest may retain noncanonical formatting. Instruction
and tool-schema references match literal streamed file identities, without parsing
their bodies. Missing/null/empty distinctions stay available from the original
document rather than reconstructed typed data.

Private literal capture now keeps those exact verified bytes in an explicitly
owned snapshot, usable after its directory or local OCI source is removed. A
single stdlib `SpooledTemporaryFile` shares a 1 MiB in-memory threshold across
captured literals, then automatically spills to anonymous/deletion-on-close
backing storage. This is a spill threshold, not a new file-size limit. Capture
streams bounded chunks, reuses already retained immutable bytes where available,
and never extracts an archive tree or reopens a source after capture returns.
Storage failures, including disk-full, are I/O errors. The snapshot holds memory
or temporary backing until explicitly closed; its private owner is a context
manager. Views and iterators become unusable after close. Byte iteration preserves
non-UTF-8 content; strict incremental text decoding can fail without changing the
verified bytes. No public package loader or package lifetime API is exposed yet.

Full owning-schema checks plus local Go declaration rules cover identities,
invocation declarations, deployment
environment names, tools, remote headers, delegated authorization and extensions.
Variants and their inventories, runtime, environment, network and dependencies
are now frozen typed records with explicit original raw fragments for identity.
Private bundled-subsystem checks bind directory-source modes, compare complete
payload inventories, validate every dependency graph and detect collisions within
caller-selected installation sets. Archive/OCI modes remain authoritative; host
access policy and permissions are unchanged. Dependency traversal does not impose
Python's process recursion limit.

Private graph prerequisites now include frozen build/runtime profiles, image and
execution records, and agent/standalone-provider compositions. Validation checks
exact reference identities and selections, image authority/digest/platform rules,
runtime harness consistency, every agent's provider resolution and invocation
targets, selected transitive installation collisions, inward retention and exact
derived capabilities. Schema checks are supplemented by Go's stricter full-string
identity/HTTP-path rules and semantic uniqueness; no runtime implementation catalog
or runtime execution is introduced. Original pinned bytes remain authoritative.

Successful private graph checks still do **not** establish finished whole-package
validation, runtime support, verified root identity or a public partial reader.
Evaluation indexes, cases, assertion operands, authored repeat fields and v1/v2
policy intent now also have frozen located records with explicit schema-first
converters (v1 uses its closed wire contract because it has no standalone schema).
Original JSON remains authoritative; policies keep their own version envelope.
Network ports check mathematical integrality against the original numeric lexeme,
not a rounded float. Evaluation namespace/regex checks and complete policy
semantics remain separate; decoding these private records is not whole-package
validation, policy enforcement or execution.

Both distribution formats carry exact bytes from the repository's owning
`schema/` tree, with schema revision, IDs and SHA-256 inventory. No runtime
schema downloads or editable Python schema copies are used.

From the repository root, with Python 3.10 or newer and Go installed:

```sh
python -m pip install -r python/requirements-dev.txt
python -m pip install ./python
python -m pytest python/tests
python -m mypy --config-file python/pyproject.toml python/src/agent_suite
```

Tests require the repository's shared JSON and variant conformance corpus;
missing, empty, truncated or unknown-target corpora fail. Go-backed numeric
differential tests retain original number spellings. Shared directory rule/access
vectors, raw gzip/tar and OCI envelope vectors, Go differential probes and a
full-scalar Go folding oracle check the native input boundary on
Linux, macOS and Windows. Go is a test reference, not a runtime dependency; Windows
bindings use only `ctypes` and `msvcrt`. Package graph validation and verified
Suite root identity are intentionally not claimed by this foundation.
