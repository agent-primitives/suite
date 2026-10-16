# Contributing to AgentSuite

Keep contributions focused: fixes, documentation, conformance tests and small
format/library changes. Discuss public contract changes before implementation.
Follow the [Code of Conduct](CODE_OF_CONDUCT.md) and report vulnerabilities using
[SECURITY.md](SECURITY.md), not public issues.

## Scope and compatibility

The normative contract is [spec.md](spec.md), with closed reference schemas in
[schema/](schema/) and conformance fixtures in [testdata/](testdata/).
The root Go package is `agentsuite`, imported as
`agentsuite "github.com/agent-primitives/suite"`.
Builders, registry transfer, runtime execution and enforcement belong to consumers.

Preserve schema IDs, media types and canonical identity unless a separately
reviewed format change explicitly requires otherwise. Test both acceptance and
refusal paths; malformed, missing, ambiguous or partial inputs must not silently
pass. Keep fixture JSON canonical and descriptor digests consistent. Validation
of stored evaluations is not evidence of executing or passing them.

Do not include credentials, private endpoints, customer data or unsanitized logs
in code, fixtures, issues or pull requests. Explain intent and constraints in
comments; keep change history in commit messages and release notes.

## Local verification

Use Go 1.26.0 or newer, Python 3.10 or newer, and actionlint.
CI uses staticcheck `2026.2.1`, matching the source repository's pinned tool.
From the repository root, run:

```bash
GOWORK=off go mod tidy -diff
GOWORK=off go test -count=1 ./...
GOWORK=off go test -race -count=1 ./...
GOWORK=off go vet ./...
go install honnef.co/go/tools/cmd/staticcheck@2026.2.1
GOWORK=off staticcheck ./...
gofmt -l .
python3 scripts/check-doc-links.py --selftest
python3 scripts/check-doc-links.py
actionlint .github/workflows/ci.yml
```

`gofmt -l .` must print no files. When adding or removing dependencies, run
`GOWORK=off go mod tidy` and review both module files. Do not commit `replace`
directives or local workspace files.

The required CI jobs are **Go and conformance** and **Documentation**: neither is
path-filtered. The Go job runs every test uncached, rejects all skipped tests and
requires explicit passing results for the existing minimal, coordinator-workers,
remote-MCP, bundled-provider, standalone-provider-composition, embedded-evaluation
and OCI conformance tests. A missing or renamed required test must not become
a green empty selection. Race tests, vet, staticcheck and formatting also gate CI.

The small offline docs checker covers local links and Markdown heading anchors
(including hidden GitHub documentation); its selftests exercise accepted and
rejected inputs. It does not fetch external URLs or implement a complete
Markdown renderer. Review external links and rendered Markdown manually too.

## Documentation site

Use Node.js 22.12 or newer. Run `npm --prefix docs ci --ignore-scripts`, then
`npm --prefix docs run docs:check` to build and test the rendered site. Use
`npm --prefix docs run docs:dev` for a loopback-only preview. Keep generated HTML,
cache and node_modules untracked; spec.md and schema/ remain authoritative.
The required **Documentation** job includes this build and its rendered checks.
See [site hosting](docs/hosting.md) for owner-only Pages/domain setup and
publication boundaries. Lint both workflows with `actionlint .github/workflows/*.yml`.

## Local development across repositories

Use an outside-tree, uncommitted workspace with both suite and its consumer.
For sibling clones at `/work/suite` and `/work/kaimahi`, for example:

```bash
cd /work
go work init ./suite ./kaimahi
GOWORK=/work/go.work go test ./suite/... ./kaimahi/...
```

The external workspace substitutes local modules for development only. Consumers
pin published immutable release versions and their sums. Release verification
must run independently with `GOWORK=off`; workspace rehearsal is not proof that
an unpublished version can be fetched.

## Release policy

Tom owns releases. The first tag is **`v0.1.0`**, at the repository root
(not `agentsuite/v0.1.0`). No tag is created by bootstrap or CI.

While the module is v0, breaking Go API changes, changes to validation acceptance,
wire shapes, canonicalization/digests or semantic-diff contracts require an
explicitly documented **minor** release. Compatible additions use a minor release;
compatible fixes use a patch release. Document compatibility effects and migration
guidance in release notes. Format/schema versions are independent of Go tags.

Before Tom creates or publishes a release:
1. Review the exact source commit and compatibility notes; require both CI jobs
   and fresh independent `GOWORK=off` verification.
2. Verify the approved maintainer team, enterprise admission, CLA checks,
   dependency/security scanning, Copilot review and branch/tag protections with
   organization administrators. These are operator-owned controls, not established
   merely by adding workflow files. Configure required checks for both CI jobs,
   PR approval/thread resolution, and no force-push or deletion.
3. Publish the reviewed immutable root tag; consumers then pin that version and
   verify clean-checkout `GOWORK=off` tests against the published module.

No approved maintainer team is recorded here, so CODEOWNERS is intentionally
deferred rather than assigning an invented roster. The extraction rehearsal
does not push, tag, open PRs or configure enterprise/repository controls.

## Pull requests

Keep one problem per PR and include exact verification commands and results.
Update the spec, schemas, docs and tests together for intentional contract
changes. Describe compatibility and identity effects explicitly. Do not claim
runtime qualification from offline fixture tests.
