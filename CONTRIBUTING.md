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
and OCI conformance tests, plus policy-binding fixture/schema/digest-propagation
coverage. Generated two-runtime-profile graph/schema and same-OCI separate-evidence
conformance tests are also required passes. A missing or renamed required test must not become
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
The required **Documentation** job includes this build, its rendered checks and
Chromium browser regressions. After building, run `npm --prefix docs exec playwright install chromium`
and `npm --prefix docs run docs:test-browser` to check mobile navigation, keyboard
focus, themes, local search, raw schema downloads and the JavaScript-free landing page.
CI installs Chromium's system dependencies with `--with-deps` as well.
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

Releases are cut by the maintainers as root tags (`vX.Y.Z`, not
`agentsuite/vX.Y.Z`). CI never creates tags.

While the module is v0, breaking Go API changes, changes to validation acceptance,
wire shapes, canonicalization/digests or semantic-diff contracts require an
explicitly documented **minor** release. Compatible additions use a minor release;
compatible fixes use a patch release. Document compatibility effects and migration
guidance in release notes. Format/schema versions are independent of Go tags.

Before a release:
1. Review the exact source commit and compatibility notes; both CI jobs must be
   green, plus an independent `GOWORK=off` verification.
2. Publish the reviewed immutable root tag. Consumers then pin that version and
   verify clean-checkout `GOWORK=off` tests against the published module.
3. Update `latestRelease` in `docs/.vitepress/release.mjs` to the published tag,
   then run `npm --prefix docs run docs:check` and
   `npm --prefix docs run docs:test-browser`. The site test requires the home-page
   status and footer labels and tag links to agree with this single constant;
   verify it against the latest published tag when reviewing a release.

## Pull requests

Keep one problem per PR and include exact verification commands and results.
Update the spec, schemas, docs and tests together for intentional contract
changes. Describe compatibility and identity effects explicitly. Do not claim
runtime qualification from offline fixture tests.
