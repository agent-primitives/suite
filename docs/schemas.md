<script setup>
import catalog from './schema-catalog.json'
</script>

# JSON schemas

Download the current main-branch schemas below. They are copied byte-for-byte
from the repository's schema directory, not rendered as HTML.

## Select a contract revision first

Use the entire schema directory from the same release as your producer or
validator. A `schemaVersion`, media type or historical `$id` alone does not
select a release: several historical releases use the same identifiers with
different validation constraints. Do not mix conflicting contract bundles in
one registry. Pin the validator/library separately from editor configuration:
a Go module pin does not configure an editor's schema registry. Registry and
editor callers SHOULD report the selected release; no new Go or TypeScript
diagnostic API is required.

| Contract source | Pinned schema directory | Notable additions |
| --- | --- | --- |
| v0.1.0 | [v0.1.0/schema](https://github.com/agent-primitives/suite/tree/v0.1.0/schema) | Original artifact and evaluation schemas |
| v0.2.0 | [v0.2.0/schema](https://github.com/agent-primitives/suite/tree/v0.2.0/schema) | Portable evaluation evidence |
| v0.3.0 / v0.3.1 | [v0.3.0/schema](https://github.com/agent-primitives/suite/tree/v0.3.0/schema) / [v0.3.1/schema](https://github.com/agent-primitives/suite/tree/v0.3.1/schema) | Agent policy binding, policy v2, experimental execution and inference |
| v0.4.0 | [v0.4.0/schema](https://github.com/agent-primitives/suite/tree/v0.4.0/schema) | Runtime profiles |
| v0.5.0 | [v0.5.0/schema](https://github.com/agent-primitives/suite/tree/v0.5.0/schema) | Frozen minor-scoped schema IDs |
| main (development) | [schema/](https://github.com/agent-primitives/suite/tree/main/schema) | Moving development contract; downloads below |

The site downloads track main, not the latest release. The historical
kaimahi.dev `$id` URLs are not a reliable way to retrieve the selected contract:
some serve immutable v0.1.0 copies and others are not hosted. For example, the
v0.1.0 Agent schema does not accept the policy binding added in v0.3.0. Fetching
that historical ID cannot validate a v0.4.0 Agent with a policy binding.
The [schema identity contract](../spec.md#54-schema-identity-and-contract-selection)
defines the minor-scoped namespace. The released v0.5.0 bundle uses frozen
`/schema/v0.5/` IDs and is listed in the published catalog below. Main uses
unstable `/schema/draft/` IDs; its downloads are not a released contract.
An ID in source does not mean its URL is published: the asset workflow,
reviewed catalog update and site deployment are separate steps. Manual tags
do not publish schema assets; maintainers prepare them with the separate
[release-asset workflow](hosting.md#schema-release-assets-and-retained-history).

## Minor-scoped identity and migration

Released IDs use `https://suite.agent-primitives.dev/schema/v0.N/<filename>.schema.json`,
with one immutable bundle per minor release. Patches MUST keep that minor's
entire schema inventory and bytes unchanged; schema changes require a minor.
Main uses explicitly unstable `/schema/draft/` IDs; drafts are never catalogued
as released contracts. Minor-release preparation rewrites them to `/schema/v0.N/`,
then main returns to draft IDs before further schema development. CI guards
must reject changes to catalogued bytes and patch bundles differing from their minor.

The first namespace move shipped in v0.5.0. The reviewed
[catalog source](https://github.com/agent-primitives/suite/blob/main/docs/schema-catalog.json) pins release assets by URL, source commit,
checksum and schema inventory and maps releases to bundles. CI rejects deletion
or mutation of existing entries, changed catalogued stable IDs, and patch
inventory/byte changes. Legacy reused IDs remain archive-scoped, not global
aliases. Pages downloads every catalogued asset only at build time; missing,
corrupt or mismatched assets fail the build rather than dropping history.
This migration changes only schema IDs, not validation constraints. Canonical
URLs become available only after asset publication, cataloguing and a verified deployment.

## Published schema bundles

<p v-if="catalog.bundles.length === 0">No schema assets are catalogued yet. Use the pinned source directories above.</p>
<ul v-else>
  <li v-for="bundle in catalog.bundles" :key="bundle.path">
    <strong>{{ bundle.path }}</strong> (source release {{ bundle.release }})
    <ul>
      <li v-for="(_, name) in bundle.schemas" :key="name"><a :href="`/schema/${bundle.path}/${name}`">{{ name }}</a></li>
    </ul>
  </li>
</ul>

The site emits the verified catalog at `/schema/catalog.json`. Stable bundles
use `/schema/v0.N/`; pre-migration archives use `/schema/archive/v0.N.P/` and
retain their original IDs. The unversioned downloads below continue to track main.

Wire-format versions remain independent of schema IDs: Suite `schemaVersion`,
evidence `schemaVersion`, policy `version` and document media types do not change
for this namespace move. Schema-document `$schema` still selects JSON Schema
2020-12. Do not add instance `$schema` or `apiVersion` to closed AgentSuite
documents or reserialize artifacts merely to select a schema.

Retain the hosted kaimahi.dev v0.1.0 schemas byte-for-byte, without redirects to
current contracts. Historical releases with reused IDs need separate,
explicitly selected release-local registries. Never install a global
old-to-latest alias or guess a contract for an unhosted historical ID.
See the [release policy](../CONTRIBUTING.md#schema-publication-policy).

## Stability boundaries

The [normative status table](../spec.md#111-stability-boundaries-and-compatibility)
names all ten manifest families and the exact experimental exceptions. The spec
still uses `1.0.0-draft`: the table describes the intended wire-1.0 stable core,
not a released stable format. Tools and `Agent.policy` are embedded fields;
the ToolProvider catalog has a normative definition but no standalone schema.
Optional runtime-profile metadata is in the stable-core scope; its opaque
`configurationABI` and actual runtime support remain consumer-owned. Normative
sandbox-binding requirements remain in scope even though their reference schema
is builder-owned.

Future optional fields are not automatically compatible with old closed readers:
unknown properties still refuse. Pin a contract and reader that support the
fields emitted. The mixed draft/stable graph ban is migration policy text only
here; it does not add stable-version acceptance or change draft acceptance.
Go API/semantic-diff compatibility, evidence/policy versions and schema namespaces
remain separate from the wire-1.0 promise.

## Suite entry point

- [suite.schema.json](../schema/suite.schema.json): root manifest and its content references.

## Agents and sandbox inputs

- [agent.schema.json](../schema/agent.schema.json): agent instructions and tool requirements.
- [tool-provider.schema.json](../schema/tool-provider.schema.json): provider contracts and variants.
- [composition.schema.json](../schema/composition.schema.json): agent and provider selections.
- [build-profile.schema.json](../schema/build-profile.schema.json): sandbox build inputs.
- [runtime-profile.schema.json](../schema/runtime-profile.schema.json): optional pinned runtime/harness/renderer requirements and configuration ABI.
- [tool-provider-composition.schema.json](../schema/tool-provider-composition.schema.json): standalone provider composition.

## Optional evaluations

- [eval-index.schema.json](../schema/eval-index.schema.json): an agent's ordered evaluation cases.
- [eval-case.schema.json](../schema/eval-case.schema.json): a case and its authored assertions.

## Portable evaluation evidence

- [eval-evidence.schema.json](../schema/eval-evidence.schema.json): external, suite-bound evaluation records.

## Experimental execution and inference contracts

- [inference.schema.json](../schema/inference.schema.json): experimental
  `Agent.model.capabilities` and all its fields. This branch selects capability
  requirements with `api: "openai-chat-completions-v1"`, rather than an exact model.
- [execution.schema.json](../schema/execution.schema.json): experimental
  `BuildProfile.execution` and all its fields, selected by the image-serving record
  with `kind: "http-v1"` and `protocol: "openai-chat-v1"`.
- Within that execution record, `configuration: "agentkit-v0-mounted-v1"`
  explicitly opts into the experimental AgentKit mounted configuration mapping.
  It is not the runtime profile's opaque `configurationABI`.

These are existing opt-in branches/selectors, not new flags. Their presence does
not select a runtime, qualify a model or establish execution support. Experimental
revisions cannot silently change stable fields, canonical identity or refusal
behavior; see the [compatibility policy](../spec.md#111-stability-boundaries-and-compatibility).

## Standalone network-only policies

- [policy-v2.schema.json](../schema/policy-v2.schema.json): authored/effective IPv4 TCP egress allowances.
- [administrative-policy-v2.schema.json](../schema/administrative-policy-v2.schema.json): optional intersecting restrictions.

The Agent schema also defines optional policy FileRefs; the validator checks
owning-Agent paths, descriptor/version agreement and closed policy graph membership.
See [Agent policy binding](../spec.md#83-agent-policy-binding).
See the [normative policy contract](../spec.md#appendix-b-standalone-policy-contracts-normative).

## Validation and identity

All use JSON Schema 2020-12. Each current schema ID is
`https://suite.agent-primitives.dev/schema/draft/` plus its actual filename,
including `policy-v2.schema.json` and `administrative-policy-v2.schema.json`.
These unstable IDs select main's development contract; use a released bundle
for stable validation constraints. Schema-document identity is separate from
instance versions, media types and artifact digests. The unversioned main
downloads do not establish canonical URL availability. Historical
kaimahi.dev IDs and hosted v0.1.0 bytes remain unchanged; older releases must
still be selected with their own complete schema bundle.

Schemas validate document shapes. The [Go validator](go.md) additionally checks
cross-document references, canonical bytes, descriptors and the closed content graph.
Policy semantics and payload verification use the `policy` package. `ValidatePath`
reuses its semantic decoder for explicitly bound authored policy files; unreferenced
files in the policy namespace refuse rather than being silently discovered or applied.

## Offline resolution recipe

Obtain a release checkout while online, then use only its local schemas. For
example, clone the immutable v0.4.0 tag and enter that checkout:

```bash
git clone --depth 1 --branch v0.4.0 https://github.com/agent-primitives/suite.git suite-v0.4.0
cd suite-v0.4.0
```

With Python `jsonschema` 4.18 or newer (which installs `referencing`), the following validates
the checked-in policy-bound Agent without fetching any schema URL:

```python
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

registry = Registry()
for path in sorted(Path("schema").glob("*.schema.json")):
    schema = json.loads(path.read_text())
    registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))

agent_schema = json.loads(Path("schema/agent.schema.json").read_text())
agent = json.loads(Path("testdata/policy-binding/agents/writer.json").read_text())
Draft202012Validator(agent_schema, registry=registry).validate(agent)
print("Agent shape is valid against v0.4.0 schemas")
```

The registry maps every declared `$id` to its release-local bytes; relative
`$ref`s resolve against those IDs. This is important for policy v2: the local
filename `policy-v2.schema.json` has an ID ending in `policy/v2/policy.schema.json`.
`Registry()` has no network retrieval callback, so an unregistered external
reference fails rather than silently downloading another revision. Configure
other validators with the equivalent local URI-to-schema registry and disable
remote retrieval, including meta-schema fetching during compilation; preload
the declared dialect too. Preserve the downloaded schema bytes and their `$id`s.
Conforming AgentSuite validation MUST NOT fetch schemas or meta-schemas over
the network and MUST fail closed on unresolved or conflicting resources.
Equivalent handwritten validation is permitted; the Go Suite and TypeScript
policy validators do not need a runtime JSON Schema engine.

Schema validation checks shape only. The example does not validate the Agent's
referenced policy contents, descriptor digests or graph closure; use the Go
validator for those checks. Pinning the Go module does not configure an editor's
schema registry, and neither `schemaVersion` nor a schema ID currently provides
automatic negotiation of the release-specific acceptance contract.
