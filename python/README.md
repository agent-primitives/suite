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
Domain readers and full validation are a later change.

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
limits apply. OCI envelope/blob loading is not included yet; a successful layer
read is not schema, graph or package-identity validation.

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
vectors, raw gzip/tar vectors and Go differential probes, and a full-scalar Go
folding oracle check the native input boundary on
Linux, macOS and Windows. Go is a test reference, not a runtime dependency; Windows
bindings use only `ctypes` and `msvcrt`. Package graph and OCI
conformance are intentionally not claimed by this foundation.
