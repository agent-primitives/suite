# Python integration

The `agent-suite` distribution imports as `agent_suite`. It reads, validates,
edits, writes and publishes AgentSuite packages. It does not execute agents or
evaluations, enforce policy, or qualify a runtime.

This page tracks **main's development SDK**, currently `0.1.0.dev0`. It does not
announce a PyPI release or claim frozen Suite v0.8.0 compatibility. A release must
pass the frozen-contract qualification described below before publication.

## Install from a checkout

From the repository root, with CPython 3.10 or newer:

```sh
python -m pip install --only-binary=google-re2 ./python
```

The native RE2 dependency is exactly pinned; unsupported platforms must not fall
back to a source build or Python `re`. The CI matrix covers Python 3.10 and 3.14
on Linux, macOS and Windows. Go is a conformance reference, not a runtime dependency.
Schemas ship as exact, offline package assets; loading never downloads schemas.

## Inspect, edit and publish

Use an extracted content directory or local OCI layout. The selected package must
contain the `writer` agent used here. Both output paths must be fresh, and their
existing parents must satisfy the native reader's ownership and permission checks.

```python
import os
from agent_suite import Package, Registry

credentials = {
    "https://registry.example": (
        os.environ["REGISTRY_USERNAME"],
        os.environ["REGISTRY_PASSWORD"],
    ),
}

with Package.load("./support-suite") as package:
    agent = package.agents["writer"]
    print(agent.declaration.id, agent.source.file, agent.source.pointer)
    instructions = "".join(agent.instructions.content.iter_text())
    package.set_instructions("writer", instructions + "\nAnswer briefly.\n")
    assert package.validate() == ()
    layout = package.write_oci("./out-layout")

reference = Registry("registry.example", credentials=credentials).publish(
    layout, "team/support"
)
print(reference)  # registry.example/team/support@sha256:...
```

`Package.load` performs complete schema and graph validation, including policy and
evaluation declarations. `validate()` checks the captured package, not a running
agent. Raw JSON mutation is unsupported; `set_instructions` refreshes the selected
literal, agent and Suite pins bottom-up and refuses a stale input graph.

After an edit, reacquire views: earlier frozen metadata remains historical, but
old literal handles are closed. To read authored JSON metadata without inventing
defaults, use `json.loads(agent.document.data)`; typed declarations and literal
content remain separate. `iter_text()` decodes UTF-8 strictly; `iter_bytes()`
preserves arbitrary literal bytes.

## Keep the identities separate

- `root_digest` is the validated Suite root's RFC 8785 identity. It is not an OCI
  address or an aggregate hash of every content file.
- `digest(value)` and `canonical_bytes(value)` use RFC 8785. `variant_digest(value)`
  blanks only the top-level `variantDigest`. Instruction and schema literals hash
  their exact bytes rather than canonicalized JSON.
- `artifact_digest` identifies the **exact OCI manifest bytes**. It is absent for
  extracted directories and cleared by edits; reload the written OCI layout for
  its new identity. `oci_manifest_digest(manifest_bytes)` hashes those exact bytes.
- `Registry.publish` returns `authority/repository@sha256:…` using that exact
  manifest identity, never `root_digest`.

Unedited OCI copies preserve their original envelope, manifest and compressed
layer. Regenerated OCI output is deterministic. Native directory writing may
refuse modes accepted in OCI; writers do not repair modes or flatten unsupported
links. No public aggregate-content identity or generic manifest builder is exposed.

## Credentials, transfer and failures

`Registry(origin, *, credentials=None, timeout=30.0)` accepts a registry authority
(defaulting to HTTPS) or an explicit HTTP(S) origin. Explicit HTTP is unencrypted;
use it only where that is intended, such as an owned loopback test registry.
Repository names are passed separately to `publish(layout, repository)`; this
method accepts a fully validated local OCI layout, not an extracted directory.

Credentials are a mapping from **exact normalized HTTP origins** to
`(username, password)` tuples. A registry token can be the password. If a Bearer
challenge uses a different token-service origin, include credentials for that
origin explicitly when it needs them; registry credentials are not copied there.
No credential files, netrc, ambient proxy credentials or response cookies are used.
The client does not expose a credential store, login flow or transport framework.

All transfer input is verified and captured into bounded-memory, seekable disk
snapshots before the first request. The source may then disappear without
changing the uploaded bytes. Config and layer blobs are uploaded before the
original manifest, addressed by digest. A final manifest read confirms exact
remote bytes before the reference is returned; it is verification of this upload,
not a registry pull API. Already-present blobs make repeated publication cheap.

Server upload locations retain their existing query parameters. Authorization is
not forwarded to a different upload origin. Bounded 307/308 redirects preserve
request methods and replay the snapshot; HTTPS is not downgraded. Other redirect
statuses and unsupported responses fail rather than changing a PUT into a GET.
No multipart, chunk-resume, background retry or registry cleanup framework exists.

Local `LoadError` refusals retain file/pointer diagnostics. Transfer failures raise
contextual `ValueError` without server bodies, secret-bearing URLs or tokens.
Failure after a remote write can leave blobs or a manifest present; it never
returns a guessed success. Retry the whole publication to confirm the same digest.

## Owner-controlled release qualification

The manual `python-release.yml` workflow takes an existing `python/vX.Y.Z` SDK tag,
a frozen `v0.8.P` Suite tag, and `publish` (default **false**). It never creates tags
or changes schema IDs. The first release requires the final SDK code and version
bump in the frozen v0.8 release commit; tag that immutable source, merge the
reviewed schema-catalog update, then dispatch qualification from main. Main can
restore draft IDs afterwards because qualification checks out both exact tags.
Frozen maintenance-branch SDK patch tags are supported without requiring ancestry
from current draft main.

Trusted tools and the reviewed catalog are pinned to the dispatch revision. They
check exact schema bytes, source/tag/version identities, wheel and sdist provenance,
and Go conformance from the selected contract revision. Test-only
`AGENTSUITE_GO_ORACLE_ROOT` selects that frozen Go checkout; it adds no runtime Go.
The downloaded wheel and sdist are re-hashed against the qualification record
before any upload.

The release owner must configure PyPI Trusted Publishing and a protected `pypi`
environment requiring that owner's approval before opting into upload. Running
qualification does not upload by default. The first PyPI upload and Suite v0.8.0
release are owner actions, not actions performed by a pull request.

## Boundaries

The SDK does not run tests, models, providers or deployment tools. Stored test and
policy validation is not execution or enforcement. There is no registry pull,
tag publication, signing, referrer, CLI, runtime wrapper or telemetry API.
