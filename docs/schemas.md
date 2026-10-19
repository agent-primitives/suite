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
| main (development) | [schema/](https://github.com/agent-primitives/suite/tree/main/schema) | Moving development contract; downloads below |

The site downloads track main, not the latest release. The historical
kaimahi.dev `$id` URLs are not a reliable way to retrieve the selected contract:
some serve immutable v0.1.0 copies and others are not hosted. For example, the
v0.1.0 Agent schema does not accept the policy binding added in v0.3.0. Fetching
that historical ID cannot validate a v0.4.0 Agent with a policy binding.
The [schema identity contract](../spec.md#54-schema-identity-and-contract-selection)
defines a minor-scoped replacement namespace. The migration has not happened:
the files and downloads below still carry historical IDs. Manual tags do not
publish schema assets; maintainers prepare them with the separate
[release-asset workflow](hosting.md#schema-release-assets-and-retained-history).

## Minor-scoped identity and migration

New stable IDs will use
`https://suite.agent-primitives.dev/schema/v0.N/<filename>.schema.json`,
with one immutable bundle per minor release. Patches MUST keep that minor's
entire schema inventory and bytes unchanged; schema changes require a minor.
Main will use explicitly unstable `/schema/draft/` IDs, never catalogued as
released contracts. Minor-release preparation rewrites them to `/schema/v0.N/`;
main returns to drafts before further schema development. CI guards must reject
changes to catalogued bytes and patch bundles differing from their minor.

The first namespace move ships in a minor release. The reviewed
[catalog source](https://github.com/agent-primitives/suite/blob/main/docs/schema-catalog.json) pins release assets by URL, source commit,
checksum and schema inventory and maps releases to bundles. CI rejects deletion
or mutation of existing entries, changed catalogued stable IDs, and patch
inventory/byte changes. Legacy reused IDs remain archive-scoped, not global
aliases. Pages downloads every catalogued asset only at build time; missing,
corrupt or mismatched assets fail the build rather than dropping history.
No namespace or schema bytes change until a separately reviewed migration.

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

- [execution.schema.json](../schema/execution.schema.json): a built image's execution interface (experimental).
- [inference.schema.json](../schema/inference.schema.json): inference requirements (experimental).

## Standalone network-only policies

- [policy-v2.schema.json](../schema/policy-v2.schema.json): authored/effective IPv4 TCP egress allowances.
- [administrative-policy-v2.schema.json](../schema/administrative-policy-v2.schema.json): optional intersecting restrictions.

The Agent schema also defines optional policy FileRefs; the validator checks
owning-Agent paths, descriptor/version agreement and closed policy graph membership.
See [Agent policy binding](../spec.md#83-agent-policy-binding).
See the [normative policy contract](../spec.md#appendix-b-standalone-policy-contracts-normative).

## Validation and identity

All use JSON Schema 2020-12. Existing artifact schema identifiers remain
`https://kaimahi.dev/schemas/agentsuite/v1/<file>.schema.json`; downloading a
schema here does not change its identifier. The standalone policy v2 additions
use `https://kaimahi.dev/schemas/agentsuite/policy/v2/` identifiers; they do not
rename any existing schema. The kaimahi.dev endpoints for schemas
included in v0.1.0 serve those immutable copies, independently of these main-branch
downloads. The portable evidence schema and the experimental execution and
inference schemas are main-branch additions, not part of v0.1.0; their
identifiers' hosting is separate from these raw downloads. Hosting of the new
policy identifiers is likewise separate from the raw downloads.

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
