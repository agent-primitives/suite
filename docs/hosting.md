# Site hosting

The site builds for **https://suite.agent-primitives.dev/** with `base: '/'`.
The default GitHub project URL under `/suite/` is not supported. Pull requests
build and test in the required **Documentation** job; only main can deploy.

## Preview and verify

Use Node.js 22.12 or newer:

```bash
npm --prefix docs ci --ignore-scripts
npm --prefix docs run docs:check
npm --prefix docs run docs:dev
```

The development server binds to loopback. The exact VitePress
`2.0.0-alpha.20` pin matches kaimahi's documentation tooling; it is a prerelease,
not a stable-framework claim. The lockfile is committed. No external fonts,
analytics, hosted search or runtime credentials are used.

The root specification is rendered in place, with GitHub-compatible heading
anchors. Schemas are copied unchanged into the build output. Fixtures link back
to source rather than becoming another maintained content tree.

## Schema release assets and retained history

The main-only `schema-assets` workflow is manually dispatched for an existing
root tag and GitHub Release. It never creates tags/releases, rewrites schemas,
executes tagged code, changes DNS, or edits the catalog. Its trusted main-branch
script reads ordinary schema blobs from the tagged commit. No npm install is
needed; write credentials are exposed only to the upload step.

Before tagging, fetch main and tags and run the pre-tag check from the trusted
main checkout against the reviewed release commit. For example,
`node scripts/schema-release.mjs check --release v0.5.1 --ref <reviewed-commit> --catalog-ref refs/remotes/origin/main`
uses an illustrative patch tag; substitute the exact commit. A stable patch
without a catalogued minor fails closed. Patch commits must retain that minor's
complete schema inventory and bytes, not main's drafts.

After maintainer tag/release approval, an operator can dispatch, for example:

```bash
gh workflow run schema-assets.yml -R agent-primitives/suite --ref main -f release=v0.4.0
```

The workflow rechecks the remote tag before upload. An existing identical asset
is left untouched; a different asset refuses rather than being overwritten.
Assets are deterministic `schemas-v0.N.P.json` bundles containing the source
commit, release and original schema text. Each schema's UTF-8 bytes are preserved.
Stable patches reuse the minor asset and propose only a new release mapping.
Old releases become full-release archives without changing their historical IDs.
A backfill needs an existing Release object: v0.1.0 needs separate owner setup.
This workflow targets existing published, mutable releases. If GitHub immutable
releases are enabled, stop: supporting a draft/upload/publish sequence needs a
separate workflow change. This workflow never changes the immutability setting.

The job prints `catalog-candidate.json` for a separate reviewed catalog PR.
For local preparation, run `node scripts/schema-release.mjs pack --release v0.4.0 --out ../schema-assets`;
this writes local files only. Merge the candidate additively into
`docs/schema-catalog.json`, never replace newer entries. Every entry pins the
asset URL, source commit, archive checksum and per-schema ID/checksum inventory.
CI checks the tag/source inventory too. The catalog starts empty; no historical
asset or canonical minor URL is implied until an operator publishes and catalogs it.

Both CI and Pages guard the catalog against the trusted Git baseline. PR checks
use the merge commit's first parent; pushes use the previous ancestor commit,
refusing zero/missing/non-ancestor values. Manual/local checks use `HEAD^` or an
explicit `--base` commit. Existing entries and release mappings cannot be deleted,
changed or retargeted. Release-line CI also checks stable schemas against main's
catalog. Full Git history/tags are needed for these checks; ordinary local
`docs:check` needs only the current catalog and its assets.

Every site build downloads **all** catalogued release assets, verifies checksums,
release/commit metadata and exact schema inventories, then copies them into
`/schema/v0.N/` or `/schema/archive/v0.N.P/`. Downloads are build-time only and
bounded; only the repository's GitHub release URLs and HTTPS release-asset CDN
redirects are accepted. No credentials are sent. Missing or corrupt assets fail
the build, preventing Pages upload/deployment and leaving the previous live
site intact. The existing unversioned main downloads stay unchanged. Verify
published URLs and checksums before announcing schema availability.

## Owner setup, in order

These are owner actions, not actions performed by the publishing workflow.

1. **Verify the apex domain for the organization before enabling the custom
   domain.** An organization owner must perform this step; organization
   membership alone is insufficient. Open the `agent-primitives` organization's
   **Settings > Pages**,
   choose **Add a domain**, and enter `agent-primitives.dev`. Add the exact TXT
   name/value GitHub provides at the DNS provider, then click **Verify**.
   The challenge name is
   `_github-pages-challenge-agent-primitives.agent-primitives.dev`; the value is
   generated by GitHub, not a value to invent. Keep that TXT record permanently.
   This protects immediate subdomains from takeover. Do not add wildcard DNS.

2. **Enable Pages using GitHub Actions before merging the site PR.** In the
   suite repository's **Settings > Pages > Build and deployment > Source**,
   select **GitHub Actions**. Equivalent API command if the Pages site does not
   yet exist:

   ```bash
   gh api --method POST repos/agent-primitives/suite/pages -f build_type=workflow
   ```

   If Pages already exists, inspect it first, then use `PUT` with
   `build_type=workflow` instead of creating it again. Leave main protection in
   place. Review any `github-pages` environment approval or branch restrictions;
   only main should deploy.

3. **Set the repository custom domain explicitly**, after org verification:
   repository **Settings > Pages > Custom domain**,
   `suite.agent-primitives.dev`, **Save**. Equivalent API command:

   ```bash
   gh api --method PUT repos/agent-primitives/suite/pages -f cname=suite.agent-primitives.dev
   ```

   The committed `CNAME` file records the intended domain, but GitHub ignores
   it for custom Actions deployments. It does not replace this settings step.

4. **Add the DNS record**, after the domain is claimed in Pages:

   | Type | Name | Target |
   | --- | --- | --- |
   | CNAME | suite | agent-primitives.github.io |

   The full record is `suite.agent-primitives.dev`. No scheme, repository path,
   apex redirect or wildcard. Verify propagation:

   ```bash
   dig +short CNAME suite.agent-primitives.dev
   ```

5. **Merge the reviewed, CI-green site PR, then rebuild after the domain is
   set.** Main pushes publish automatically. Explicitly run the workflow on
   main after domain configuration, even if an earlier deployment already ran:

   ```bash
   gh workflow run docs-pages.yml -R agent-primitives/suite --ref main
   gh run list -R agent-primitives/suite --workflow docs-pages.yml --limit 3
   ```

   Inspect that run and wait for deployment success. Every build remains at
   root `/`; no dependency on `configure-pages`' inferred project base path.

6. **Wait for the certificate, then enforce HTTPS.** In repository Pages
   settings select **Enforce HTTPS** when available (certificate provisioning
   can take up to 24 hours). Equivalent API command once ready:

   ```bash
   gh api --method PUT repos/agent-primitives/suite/pages -F https_enforced=true
   gh api repos/agent-primitives/suite/pages --jq '{build_type,cname,protected_domain_state,https_enforced,https_certificate}'
   curl --fail --show-error --silent --head https://suite.agent-primitives.dev/
   curl --fail --show-error --silent https://suite.agent-primitives.dev/spec >/dev/null
   curl --fail --show-error --silent https://suite.agent-primitives.dev/schema/agent.schema.json
   ```

For removal, remove the DNS CNAME before disabling Pages or releasing the custom
domain; retain the org verification TXT. No DNS/settings changes are automated
by CI. Pages and OIDC write permissions belong only to the deployment job.
Custom response headers are controlled by Pages, not by this static artifact.

Official references: [domain verification](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/verifying-your-custom-domain-for-github-pages),
[custom domains](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site),
and [Pages REST API](https://docs.github.com/en/rest/pages/pages).
