# Experimental critical serial flow

This is an opt-in contract under [spec §6.3](../spec.md#63-experimental-critical-flow), not stable wire-1.0 or runtime support. Stable graduation belongs to [#30](https://github.com/agent-primitives/suite/issues/30); experimental delivery under [#35](https://github.com/agent-primitives/suite/issues/35) does not wait for it.

## Selection and identity

Core documents keep `schemaVersion: "1.0.0-draft"`. The original Suite MUST contain exactly one root extension named `kmx.flow.v1alpha1`, `critical: true`, with `digest: F`. F is SHA-256 of the original RFC 8785 JCS bytes of the regular file `coordination/flow.json`, at most 4 MiB. The experimental namespace owns exactly that file and its parent directory; additional entries, links, missing/mismatched digests and noncanonical storage refuse. No new core manifest family/media type is added.

Only these fixed Go APIs select this contract **before** validation:

- `ValidatePathFlowV1Alpha1`: ordinary bounded directory/OCI auto-detection.
- `ValidateDirectoryFlowV1Alpha1`: ordinary bounded directory loading only.
- `VerifyEvaluationFlowV1Alpha1`: unchanged evidence-v1 member verification against the original OCI artifact and independent expectations.

`FlowV1Alpha1Graph.Flow()`, `.FlowDigest()` and `.Report()` expose copied definitions/core inventory, not mutable validation authority. Default `ValidatePath`, `ValidateDirectory` and `VerifyEvaluation` still refuse the same critical artifact. No stripping/rewrite, generic extension registry or error-driven fallback is permitted. Other critical names and this critical name at foreign scopes remain unsupported.

## Closed payload

See the [reference schema](../schema/kmx-flow-v1alpha1.schema.json) and [canonical two-member example](../testdata/flow-v1alpha1/flow.json). Payload `schemaVersion` is independently `kmx.flow/v1alpha1`; `id`, `mode: "pipeline"`, `entry`, `edgeRequirements`, `steps` and `cases` are required/non-null. Unknown/duplicate fields and explicit nulls refuse at every level.

Exactly two ordered steps have unique IDs, existing core member IDs, an input and optional approval. The first member equals `entry`; its source is `run.input`. Other sources are only `run.input` or an earlier `STEP.output`. Optional context is only `run.input`; forward/self references and templates are unsupported. Members can occur more than once; storage validation is not the first consumer's narrower two-distinct-member qualification.

A step's optional `approval` and each edge requirement's required `approval` are `required` or `policy-controlled`. Each `{from,to,approval}` references an existing declared `Agent.invokes` edge; duplicate pairs refuse. Empty `edgeRequirements: []` is valid. Never emit a draft `Agent.invokes[].approval` field: that frozen grammar remains unchanged.

Cases have unique IDs, nonblank input, optional positive `runs`/`minPasses`, and ordered assertions `{step,check}`. Omitted runs means one; omitted minPasses means all runs. MinPasses requires runs and cannot exceed it. Check IDs are unique per case and steps must exist. Checks reuse unchanged `EvaluationAssertion` operand/criticality rules but initially permit only `contains`, `notContains` and RE2 `regex`; no tool/judge/unknown checks. Missing coverage is never inferred from PASS text.

Limits are 128 combined member+flow cases, 1,000 runs per case, 4,096 combined runs, 1,000 assertions per case and 32,000 combined assertion observations. Existing strict JSON depth/member/number/UTF-8 limits apply. These opt-in aggregate limits do not tighten default draft acceptance.

## Experimental delegation and approval semantics

The following requirements apply **only when this contract is selected**. They are future runtime conformance obligations, not enforcement implemented by this reader:

- `maxConcurrent` bounds outstanding invocations per **calling session and declared edge**, not globally across all callers. Resume preserves the same session's accounting. An uncertain dispatch/settlement retains its slot until proven settled; retries do not create a fresh allowance.
- `maxDepth` bounds descendants through that edge. Every inherited ancestor bound remains effective: a descendant's larger local bound cannot reset an exhausted ancestor allowance.
- An authored required step/edge gate cannot be removed by deployment policy. Deployment may add gates or narrow permission, never grant undeclared invocation edges. An unknown/unimplemented required gate refuses before dispatch.
- Reviewer PASS/BLOCK is an observation, never human approval or permission to publish/Apply. No provider credential, endpoint, Task UID or mutable destination binding belongs in the artifact.

### Runtime conformance vectors (not executable runtime qualification)

| Vector | Initial state / operation | Required result |
| --- | --- | --- |
| Two callers | Edge A→B has maxConcurrent=1. Session X has one outstanding; X starts another, then session Y starts its first. | Reject X's second; allow Y subject to independent policy/bounds. |
| Resume | Resume X with the same one outstanding A→B reservation. | Still reject a second; a restart is not a new caller/session. |
| Unsettled dispatch | X's first dispatch acknowledgement/settlement is unknown, then X retries. | Retain X's slot and refuse another dispatch; no expiry/adoption/force-clear shortcut. |
| Ancestor depth | A→B maxDepth=2; B→C maxDepth=3; C→D maxDepth=9. | B and C may be reached; refuse D because A's depth budget is exhausted. |
| Deployment-added approval | Authored gate is policy-controlled; selected deployment requires approval. | Require that gate. Also preserve any authored required gate when deployment omits it. |

The first kmx consumer remains an **external serial runner**, with two tool-free/policy-free unprofiled Orka members, empty `invokes`, no required gates, and actual first output passed to the second. It MUST refuse unsupported native delegation, required gates, Sessions and kagent before execution, not simulate enforcement from these vectors.

## Evidence and publication

One immutable OCI manifest digest S binds every member and the flow; changing any member/flow stales every S-bound proof. Member verification retains evidence-v1 bytes/fields, exact original S, member/composition/build/index/case coverage/order, evaluator policy and independent execution expectations. The consumer's opaque non-secret execution-configuration projection binds exact destination B; the reader does not resolve B or authenticate unsigned claims.

This API verifies **one member only**. The consumer must independently bind every member and interaction to the same `(S,F,B)` and require all of them before publication/Apply. A member receipt is not whole-suite success, and static reviewer bad-draft cases are not actual writer→reviewer interaction evidence.

Additive draft schema publication still requires an available **minor** module release, immutable tagged schema bundle, append-only reviewed catalog and served-byte verification. Existing published bundles stay byte-identical; do not pick a tag or imply release/qualification from this document.
