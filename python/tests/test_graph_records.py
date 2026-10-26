"""Schema-owned graph record decoding, without profile or graph semantics."""
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agent_suite import _records as records
from agent_suite._models import Descriptor, Document, Platform, Source
from agent_suite._record_decode import DocumentError, read_document
from agent_suite._schema import Bundle

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("BuildProfile", "RuntimeProfile", "Composition", "ToolProviderComposition")


@pytest.fixture(scope="module")
def bundle():
    return Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / "schema").glob("*.json")})


def document(kind):
    paths = {
        "BuildProfile": "minimal/build-profiles/default.json",
        "Composition": "minimal/compositions/writer-linux-amd64.json",
        "ToolProviderComposition": "tool-providers/opa-tool-provider-composition.json",
    }
    if kind in paths:
        path = paths[kind]
        return Document.from_bytes((ROOT / "testdata" / path).read_bytes(), Source(path, "/authored"))
    # Runtime profiles are generated in Go tests, not stored as static fixtures.
    return Document.from_bytes(json.dumps({
        "schemaVersion": "1.0.0-draft",
        "mediaType": "application/vnd.agentsuite.runtime.profile.v1+json",
        "id": "native-v1",
        "runtime": {"id": "runtime", "version": "release-1", "digest": "sha256:" + "a" * 64},
        "harness": {"id": "harness", "version": "build-2", "digest": "sha256:" + "b" * 64},
        "renderer": {"id": "renderer", "version": "revision-3", "digest": "sha256:" + "c" * 64},
        "configurationABI": "consumer-v1", "imageRequired": False,
    }).encode(), Source("runtime-profile.json", "/authored"))


def changed(doc, **fields):
    return Document.from_bytes(json.dumps({**json.loads(doc.data), **fields}).encode(), doc.source)


def execution():
    return {"kind": "http-v1", "protocol": "openai-chat-v1", "port": 8080,
            "healthPath": "/healthz", "inputs": [
                {"name": "public", "environment": "PUBLIC_VALUE", "secret": False},
                {"name": "credential", "environment": "API_TOKEN", "secret": True},
            ]}


def complete(kind):
    doc = document(kind)
    if kind == "BuildProfile":
        return changed(doc, execution=execution())
    if kind == "Composition":
        provider = json.loads(document("ToolProviderComposition").data)
        return changed(doc, toolProviders=[{
            field: provider[field] for field in ("id", "version", "manifestDigest", "variantDigest")
        } | {"executionMode": "shared-sandbox"}])
    return doc


def test_build_profile_nested_records_are_frozen_located_and_typed(bundle):
    doc = complete("BuildProfile")
    loaded = read_document(doc, records.BuildProfile, bundle)
    profile = loaded.record
    assert loaded.document is doc
    assert (profile.schema_version, profile.media_type, profile.id, profile.source_epoch) == (
        "1.0.0-draft", "application/vnd.agentsuite.build.profile.v1+json", "default", 1)
    assert type(profile.source_epoch) is int
    assert isinstance(profile.runtime_base, tuple) and isinstance(profile.harness, tuple)
    for field in ("runtime_base", "harness"):
        image = getattr(profile, field)[0]
        assert isinstance(image, records.PlatformImage)
        assert image.platform == Platform("linux", "amd64")
        assert isinstance(image.image, Descriptor) and image.image.size == 1
        assert image.image_ref.endswith("@" + image.image.digest)
    contract = profile.execution
    assert isinstance(contract, records.ExecutionContract)
    assert (contract.configuration, contract.kind, contract.protocol, contract.port, contract.health_path) == (
        "", "http-v1", "openai-chat-v1", 8080, "/healthz")
    assert isinstance(contract.inputs, tuple)
    assert [(i.name, i.environment, i.secret) for i in contract.inputs] == [
        ("public", "PUBLIC_VALUE", False), ("credential", "API_TOKEN", True)]
    assert all(isinstance(i, records.ExecutionInput) for i in contract.inputs)
    for value, pointer in ((profile, ""), (profile.runtime_base[0], "/runtimeBase/0"),
                           (profile.harness[0], "/harness/0"), (contract, "/execution"),
                           (contract.inputs[0], "/execution/inputs/0")):
        assert isinstance(value, records.Located)
        assert value.source == Source(doc.source.file, "/authored" + pointer)
        with pytest.raises(FrozenInstanceError):
            value.source = Source("changed")
    raw = doc.value
    raw["execution"]["inputs"].clear()
    assert len(contract.inputs) == len(doc.value["execution"]["inputs"]) == 2
    assert loaded.document.data == doc.data


def test_build_optional_execution_and_empty_inputs_preserve_authored_presence(bundle):
    doc = document("BuildProfile")
    loaded = read_document(doc, records.BuildProfile, bundle)
    assert loaded.record.execution is None
    assert "execution" not in loaded.document.value
    doc = changed(doc, execution={**execution(), "inputs": []})
    loaded = read_document(doc, records.BuildProfile, bundle)
    assert loaded.record.execution.inputs == ()
    assert loaded.record.execution.configuration == ""
    assert "configuration" not in loaded.document.value["execution"]
    assert loaded.document is doc


def test_runtime_implementations_preserve_opaque_versions_and_required_false(bundle):
    doc = document("RuntimeProfile")
    loaded = read_document(doc, records.RuntimeProfile, bundle)
    profile = loaded.record
    assert (profile.schema_version, profile.media_type, profile.id, profile.configuration_abi) == (
        "1.0.0-draft", "application/vnd.agentsuite.runtime.profile.v1+json", "native-v1", "consumer-v1")
    assert profile.image_required is False
    for field, version, digit in (("runtime", "release-1", "a"), ("harness", "build-2", "b"),
                                   ("renderer", "revision-3", "c")):
        implementation = getattr(profile, field)
        assert isinstance(implementation, records.Implementation)
        assert (implementation.id, implementation.version, implementation.digest) == (
            field, version, "sha256:" + digit * 64)
        assert implementation.source == Source(doc.source.file, "/authored/" + field)
        with pytest.raises(FrozenInstanceError):
            implementation.id = "changed"
    with pytest.raises(FrozenInstanceError):
        profile.image_required = True
    assert loaded.document is doc
    assert read_document(changed(doc, imageRequired=True), records.RuntimeProfile, bundle).record.image_required is True


def test_composition_resolved_subrecords_and_optional_selector(bundle):
    doc = complete("Composition")
    loaded = read_document(doc, records.Composition, bundle)
    composition = loaded.record
    assert (composition.schema_version, composition.media_type, composition.agent, composition.build_profile) == (
        "1.0.0-draft", "application/vnd.agentsuite.composition.v1+json", "writer", "default")
    assert composition.platform == Platform("linux", "amd64")
    assert composition.runtime_profile == ""
    assert "runtimeProfile" not in loaded.document.value
    assert isinstance(composition.tool_providers, tuple)
    provider = composition.tool_providers[0]
    assert isinstance(provider, records.ResolvedToolProvider)
    assert (provider.id, provider.version, provider.manifest_digest, provider.variant_digest, provider.execution_mode) == (
        "opa", "1.0.0", "sha256:" + "d" * 64, "sha256:" + "a" * 64, "shared-sandbox")
    assert provider.source == Source(doc.source.file, "/authored/toolProviders/0")
    assert composition.source == doc.source
    for value in (composition, provider):
        with pytest.raises(FrozenInstanceError):
            value.source = Source("changed")
    assert loaded.document is doc
    assert read_document(document("Composition"), records.Composition, bundle).record.tool_providers == ()
    selected = read_document(changed(doc, runtimeProfile="native-v1"), records.Composition, bundle)
    assert selected.record.runtime_profile == "native-v1"
    assert selected.document.value["runtimeProfile"] == "native-v1"


def test_explicit_configuration_and_standalone_provider_composition(bundle):
    doc = changed(document("BuildProfile"), execution={**execution(), "configuration": "agentkit-v0-mounted-v1"})
    assert read_document(doc, records.BuildProfile, bundle).record.execution.configuration == "agentkit-v0-mounted-v1"
    doc = document("ToolProviderComposition")
    loaded = read_document(doc, records.ToolProviderComposition, bundle)
    record = loaded.record
    assert (record.schema_version, record.media_type, record.id, record.version, record.manifest_digest,
            record.variant_digest, record.build_profile) == (
        "1.0.0-draft", "application/vnd.agentsuite.tool.provider.composition.v1+json", "opa", "1.0.0",
        "sha256:" + "d" * 64, "sha256:" + "a" * 64, "default")
    assert record.platform == Platform("linux", "amd64")
    assert record.source == doc.source and loaded.document is doc
    with pytest.raises(FrozenInstanceError):
        record.id = "changed"


@pytest.mark.parametrize("kind", KINDS)
def test_full_owning_schema_runs_before_conversion(bundle, kind):
    doc = changed(document(kind), schemaVersion="unsupported")
    with pytest.raises(DocumentError) as error:
        read_document(doc, getattr(records, kind), bundle)
    assert error.value.diagnostics[0].code == "schema.const"
    assert error.value.diagnostics[0].source == Source(doc.source.file, "/authored/schemaVersion")


@pytest.mark.parametrize("kind,path", [
    ("BuildProfile", ("execution",)), ("BuildProfile", ("execution", "inputs")),
    ("BuildProfile", ("execution", "inputs", 0, "secret")),
    ("RuntimeProfile", ("imageRequired",)), ("RuntimeProfile", ("runtime", "digest")),
    ("Composition", ("toolProviders", 0, "variantDigest")),
    ("ToolProviderComposition", ("manifestDigest",)),
])
@pytest.mark.parametrize("omit", [False, True])
def test_required_and_optional_presence_is_not_silently_defaulted(bundle, kind, path, omit):
    doc = complete(kind)
    tree = json.loads(doc.data)
    owner = tree
    for part in path[:-1]:
        owner = owner[part]
    if omit:
        del owner[path[-1]]
    else:
        owner[path[-1]] = None
    doc = Document.from_bytes(json.dumps(tree).encode(), doc.source)
    if omit and path == ("execution",):
        assert read_document(doc, getattr(records, kind), bundle).record.execution is None
    else:
        with pytest.raises(DocumentError) as error:
            read_document(doc, getattr(records, kind), bundle)
        assert error.value.diagnostics[0].code.startswith("schema.")
        # Required-property diagnostics locate the containing object.
        diagnostic_path = path[:-1] if omit else path
        pointer = "/authored" + "".join("/" + str(part) for part in diagnostic_path)
        assert error.value.diagnostics[0].source.pointer == pointer


@pytest.mark.parametrize("kind,field", [("Composition", "runtimeProfile"), ("BuildProfile", "configuration")])
@pytest.mark.parametrize("value", [None, ""])
def test_present_optional_selectors_reject_null_and_empty(bundle, kind, field, value):
    doc = complete(kind)
    tree = json.loads(doc.data)
    owner = tree if field == "runtimeProfile" else tree["execution"]
    owner[field] = value
    with pytest.raises(DocumentError) as error:
        read_document(Document.from_bytes(json.dumps(tree).encode(), doc.source), getattr(records, kind), bundle)
    assert error.value.diagnostics[0].code.startswith("schema.")


@pytest.mark.parametrize("kind,path", [
    *((kind, ()) for kind in KINDS),
    ("BuildProfile", ("runtimeBase", 0)), ("BuildProfile", ("runtimeBase", 0, "platform")),
    ("BuildProfile", ("harness", 0, "image")), ("BuildProfile", ("execution",)),
    ("BuildProfile", ("execution", "inputs", 0)), ("RuntimeProfile", ("renderer",)),
    ("Composition", ("toolProviders", 0)),
])
def test_graph_records_reject_unknown_fields_at_nested_boundary(bundle, kind, path):
    doc = complete(kind)
    tree = json.loads(doc.data)
    owner = tree
    for part in path:
        owner = owner[part]
    owner["unexpected"] = True
    with pytest.raises(DocumentError) as error:
        read_document(Document.from_bytes(json.dumps(tree).encode(), doc.source), getattr(records, kind), bundle)
    diagnostic = error.value.diagnostics[0]
    assert diagnostic.code == "schema.additionalProperties"
    assert diagnostic.source.pointer == "/authored" + "".join("/" + str(part) for part in path)


@pytest.mark.parametrize("lexeme", ["1.0", "1e0", "9223372036854775808"])
@pytest.mark.parametrize("field", ["sourceEpoch", "size"])
def test_build_integers_require_original_lexeme_and_int64(bundle, field, lexeme):
    doc = document("BuildProfile")
    data = doc.data.replace(('"' + field + '":1').encode(), ('"' + field + '":' + lexeme).encode(), 1)
    with pytest.raises(DocumentError) as error:
        read_document(Document.from_bytes(data, doc.source), records.BuildProfile, bundle)
    diagnostic = error.value.diagnostics[0]
    assert diagnostic.code == "document.integer"
    suffix = "/sourceEpoch" if field == "sourceEpoch" else "/harness/0/image/size"
    assert diagnostic.source.pointer == "/authored" + suffix


def test_source_epoch_preserves_large_jcs_stable_integer_without_rewriting_document(bundle):
    doc = changed(document("BuildProfile"), sourceEpoch=9007199254740992)
    loaded = read_document(doc, records.BuildProfile, bundle)
    assert loaded.record.source_epoch == 9007199254740992
    assert loaded.document is doc
