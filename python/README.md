# AgentSuite Python implementation

Internal format foundation under development. There is no public package reader,
writer, registry transport or executable API yet. Do not upload this development
distribution to PyPI.

Private modules provide strict JSON decoding, RFC 8785 canonicalization, explicit
literal-byte hashes, raw-preserving common records and offline schema-only
diagnostics. Schema checks alone do not validate a package's graph or qualify a
runtime. Bundles must resolve every schema reference, even in optional branches;
diagnostics retain pointers and constraint codes without copying instance values.
Domain readers and full validation are a later change.

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
differential tests retain original number spellings. Package graph and OCI
conformance are intentionally not claimed by this foundation.
