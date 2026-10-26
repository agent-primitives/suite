"""Authored variant snapshots are typed without replacing original identity bytes."""
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agent_suite import _records as records
from agent_suite._json import Number
from agent_suite._models import Descriptor, Document, Platform, Source
from agent_suite._record_decode import DocumentError, read_document
from agent_suite._schema import Bundle

ROOT = Path(__file__).resolve().parents[2]
PROVIDER = "rich-evaluations/tool-providers/lookup/1.0.0/tool-provider.json"


@pytest.fixture(scope="module")
def bundle():
    return Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / "schema").glob("*.json")})


def provider_document(change=None):
    data = (ROOT / "testdata" / PROVIDER).read_bytes()
    if change is not None:
        tree = json.loads(data)
        change(tree["variants"][0])
        data = json.dumps(tree).encode()
    return Document.from_bytes(data, Source(PROVIDER, "/authored"))


def variant_record(bundle, change=None):
    return read_document(provider_document(change), records.ToolProvider, bundle).record.variants[0]


def test_rich_fixture_variant_defaults_are_typed_and_located(bundle):
    variant = variant_record(bundle)
    assert isinstance(variant, records.ToolProviderVariant)
    assert isinstance(variant, records.Located)
    assert variant.source == Source(PROVIDER, "/authored/variants/0")
    assert variant.platform == Platform("linux", "amd64")
    assert variant.variant_digest == "sha256:8fa188685a9216bf2accee8025a50c88e2027e677f41c156dc87d8877fc507a6"
    assert variant.install_root == "/opt/agentsuite/tool-providers/lookup"
    assert variant.payload_root == "tool-providers/lookup/1.0.0/linux-amd64"
    assert variant.entrypoint == "/opt/agentsuite/tool-providers/lookup/bin/lookup"
    assert variant.relocatable is False
    assert variant.arguments == variant.search_path == variant.writable_paths == ()
    assert variant.environment == variant.network == variant.dependencies == ()
    assert variant.sbom is variant.provenance is None
    assert isinstance(variant.runtime, records.RuntimeRequirement)
    assert variant.runtime.abi == "static"
    assert variant.runtime.abi_version == ""
    assert variant.runtime.cpu_baseline == "x86-64-v1"
    assert variant.runtime.required_base_paths == ()
    assert variant.runtime.source == Source(PROVIDER, "/authored/variants/0/runtime")
    entry = variant.files[0]
    assert isinstance(variant.files, tuple)
    assert isinstance(entry, records.InventoryEntry)
    assert entry.path == "bin/lookup" and entry.type == "file"
    assert (entry.mode, entry.uid, entry.gid, entry.size) == (493, 0, 0, 45)
    assert all(type(v) is int for v in (entry.mode, entry.uid, entry.gid, entry.size))
    assert entry.digest == "sha256:9e24b8ca3385c586ecc9b467ee6f9f8f23539fc0db584dd5949fe1c0c445193b"
    assert entry.link_target == "" and entry.component == "lookup"
    assert entry.source == Source(PROVIDER, "/authored/variants/0/files/0")


def nested_fields(variant):
    variant.update(
        relocatable=True,
        arguments=["--stdio", ""],
        searchPath=["/opt/bin"],
        writablePaths=["/tmp/cache"],
        environment=[{"name": "CACHE"},
                     {"name": "TOKEN", "required": True, "secret": True, "delivery": "file"}],
        network=[{"scheme": "https", "host": "example.org", "port": 443}],
        runtime={"abi": "gnu", "abiVersion": "2.31", "cpuBaseline": "x86-64-v2",
                 "requiredBasePaths": ["/lib", "/usr/lib"]},
        dependencies=[{"id": "helper", "version": "2.0.0", "variantDigest": "sha256:" + "a" * 64}],
        sbom={"mediaType": "application/spdx+json", "digest": "sha256:" + "b" * 64,
              "size": 0, "annotations": {"kind": "inventory"}},
        provenance={"mediaType": "application/json", "digest": "sha256:" + "c" * 64, "size": 1},
    )


def test_variant_converts_all_nested_fields_and_optional_descriptors(bundle):
    variant = variant_record(bundle, nested_fields)
    assert variant.relocatable is True
    assert variant.arguments == ("--stdio", "")
    assert variant.search_path == ("/opt/bin",)
    assert variant.writable_paths == ("/tmp/cache",)
    plain, secret = variant.environment
    assert isinstance(plain, records.EnvironmentName)
    assert (plain.name, plain.required, plain.secret, plain.delivery) == ("CACHE", False, False, "")
    assert (secret.name, secret.required, secret.secret, secret.delivery) == ("TOKEN", True, True, "file")
    assert secret.source == Source(PROVIDER, "/authored/variants/0/environment/1")
    access = variant.network[0]
    assert isinstance(access, records.NetworkAccess)
    assert (access.scheme, access.host, access.port) == ("https", "example.org", 443)
    assert type(access.port) is int
    assert access.source == Source(PROVIDER, "/authored/variants/0/network/0")
    assert variant.runtime.abi_version == "2.31"
    assert variant.runtime.required_base_paths == ("/lib", "/usr/lib")
    dependency = variant.dependencies[0]
    assert isinstance(dependency, records.ToolProviderDependency)
    assert (dependency.id, dependency.version, dependency.variant_digest) == ("helper", "2.0.0", "sha256:" + "a" * 64)
    assert dependency.source == Source(PROVIDER, "/authored/variants/0/dependencies/0")
    assert variant.sbom == Descriptor("application/spdx+json", "sha256:" + "b" * 64, 0, (("kind", "inventory"),))
    assert variant.provenance == Descriptor("application/json", "sha256:" + "c" * 64, 1)
    for value, field in [(variant, "entrypoint"), (secret, "required"), (access, "port"),
                         (variant.runtime, "abi"), (variant.files[0], "mode"), (dependency, "id"),
                         (variant.sbom, "size"), (variant.platform, "os")]:
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, None)


def test_explicit_false_zero_and_absence_remain_distinct_in_raw(bundle):
    def change(variant):
        variant["relocatable"] = False
        variant["environment"] = [{"name": "PLAIN", "required": False, "secret": False}]
        variant["files"] = [
            {"path": "empty", "type": "file", "mode": 0, "uid": 0, "gid": 0,
             "size": 0, "digest": "sha256:" + "0" * 64},
            {"path": "dir", "type": "directory", "mode": 0, "uid": 0, "gid": 0},
            {"path": "sym", "type": "symlink", "mode": 511, "uid": 0, "gid": 0, "linkTarget": "empty"},
            {"path": "hard", "type": "hardlink", "mode": 0, "uid": 0, "gid": 0,
             "size": 0, "linkTarget": "empty"},
        ]
    variant = variant_record(bundle, change)
    assert variant.relocatable is False
    assert variant.environment[0].required is variant.environment[0].secret is False
    assert [f.size for f in variant.files] == [0, 0, 0, 0]
    assert [f.link_target for f in variant.files] == ["", "", "empty", "empty"]
    assert [f.digest for f in variant.files[1:]] == ["", "", ""]
    assert all(f.component == "" for f in variant.files)
    raw = variant.raw.value
    assert raw["relocatable"] is False
    assert raw["environment"][0] == {"name": "PLAIN", "required": False, "secret": False}
    assert isinstance(raw["files"][0]["size"], Number)
    assert raw["files"][0]["size"].lexeme == "0"
    assert "size" not in raw["files"][1] and "size" not in raw["files"][2]
    assert raw["files"][3]["size"].lexeme == "0"
    raw["files"].clear()
    assert len(variant.raw.value["files"]) == len(variant.files) == 4


@pytest.mark.parametrize("field,lexeme", [
    ("mode", "493.0"), ("uid", "0e0"), ("gid", "-0.0"),
    ("size", "45e0"), ("size", "9223372036854775808"),
])
def test_inventory_integers_retain_lexeme_and_int64_checks(bundle, field, lexeme):
    doc = provider_document()
    tree = json.loads(doc.data)
    tree["variants"][0]["files"][0][field] = "LEXEME"
    raw = json.dumps(tree).replace('"LEXEME"', lexeme).encode()
    with pytest.raises(DocumentError) as error:
        read_document(Document.from_bytes(raw, doc.source), records.ToolProvider, bundle)
    diagnostic = error.value.diagnostics[0]
    assert diagnostic.code == "document.integer"
    assert diagnostic.source == Source(PROVIDER, "/authored/variants/0/files/0/" + field)


@pytest.mark.parametrize("owner,field,lexeme,pointer", [
    ("network", "port", "443.0", "/network/0/port"),
    ("sbom", "size", "0e0", "/sbom/size"),
    ("provenance", "size", "9223372036854775808", "/provenance/size"),
])
def test_nested_integer_refusals_point_to_authored_field(bundle, owner, field, lexeme, pointer):
    tree = json.loads(provider_document(nested_fields).data)
    target = tree["variants"][0][owner]
    if isinstance(target, list):
        target = target[0]
    target[field] = "LEXEME"
    raw = json.dumps(tree).replace('"LEXEME"', lexeme).encode()
    with pytest.raises(DocumentError) as error:
        read_document(Document.from_bytes(raw, Source(PROVIDER, "/authored")), records.ToolProvider, bundle)
    assert error.value.diagnostics[0].code == "document.integer"
    assert error.value.diagnostics[0].source == Source(PROVIDER, "/authored/variants/0" + pointer)


@pytest.mark.parametrize("owner,field", [
    (None, "relocatable"), (None, "sbom"), (None, "provenance"),
    ("environment", "required"), ("environment", "secret"),
    ("runtime", "abiVersion"), ("files", "size"), ("files", "component"),
])
def test_present_null_is_not_a_missing_default(bundle, owner, field):
    def change(variant):
        nested_fields(variant)
        target = variant if owner is None else variant[owner]
        if isinstance(target, list):
            target = target[0]
        target[field] = None
    with pytest.raises(DocumentError) as error:
        variant_record(bundle, change)
    assert all(d.code.startswith("schema.") for d in error.value.diagnostics)
    assert any(d.source.pointer.startswith("/authored/variants/0") for d in error.value.diagnostics)


def test_full_provider_schema_precedes_variant_integer_conversion(bundle):
    tree = json.loads(provider_document().data)
    tree["variants"][0]["files"][0]["mode"] = 493.0
    tree["variants"][0]["runtime"]["abiVersion"] = ""
    with pytest.raises(DocumentError) as error:
        read_document(Document.from_bytes(json.dumps(tree).encode(), Source(PROVIDER)), records.ToolProvider, bundle)
    assert error.value.diagnostics[0].code == "schema.minLength"
    assert error.value.diagnostics[0].source.pointer == "/variants/0/runtime/abiVersion"
