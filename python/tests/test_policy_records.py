"""Private authored policy decoding preserves bytes, locations and exact ports."""
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agent_suite import _records as records
from agent_suite._models import Document, Source
from agent_suite._record_decode import DocumentError, read_document
from agent_suite._schema import Bundle

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bundle():
    return Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / "schema").glob("*.json")})


def policy(profile=2, **changes):
    value = {"version": f"agentsuite.policy/v{profile}",
             "requiredCapabilities": ["network/egress-allow/v1" if profile == 2 else "filesystem/deny-write/v1"]}
    value.update({"network": {"egressAllow": []}} if profile == 2 else {"denyWritePaths": ["/z", "/a", "/z"]})
    value.update(changes)
    return Document.from_bytes(json.dumps(value, indent=2).encode() + b" \n", Source("policies/writer.json", "/authored"))


def port_document(token):
    data = ('{"version":"agentsuite.policy/v2","requiredCapabilities":["network/egress-allow/v1"],'
            '"network":{"egressAllow":[{"address":"192.0.2.1","protocol":"TCP","port":' + token + '}]}}').encode()
    return Document.from_bytes(data, Source("policies/writer.json"))


def test_private_policy_records_are_frozen_located_and_keep_raw_bytes(bundle):
    doc = policy(1)
    loaded = read_document(doc, records.PolicyV1, bundle)
    assert loaded.document is doc
    assert loaded.document.data.endswith(b" \n")
    assert loaded.record.version == "agentsuite.policy/v1"
    assert loaded.record.deny_write_paths == ("/z", "/a", "/z")
    assert loaded.record.required_capabilities == ("filesystem/deny-write/v1",)
    assert loaded.record.source == Source("policies/writer.json", "/authored")
    with pytest.raises(FrozenInstanceError):
        loaded.record.version = "changed"
    doc.value["denyWritePaths"].clear()
    assert loaded.record.deny_write_paths == ("/z", "/a", "/z")


def test_policy_v2_nested_sources_order_duplicates_and_empty_list(bundle):
    endpoints = [{"address": "192.0.2.2", "protocol": "TCP", "port": 443},
                 {"address": "192.0.2.1", "protocol": "TCP", "port": 80},
                 {"address": "192.0.2.2", "protocol": "TCP", "port": 443}]
    doc = policy(network={"egressAllow": endpoints})
    loaded = read_document(doc, records.PolicyV2, bundle)
    assert loaded.document is doc
    network = loaded.record.network
    assert isinstance(network, records.PolicyNetwork)
    assert network.source.pointer == "/authored/network"
    assert tuple(e.address for e in network.egress_allow) == ("192.0.2.2", "192.0.2.1", "192.0.2.2")
    assert isinstance(network.egress_allow[1], records.PolicyEndpoint)
    assert network.egress_allow[1].source == Source(doc.source.file, "/authored/network/egressAllow/1")
    assert (network.egress_allow[1].protocol, network.egress_allow[1].port) == ("TCP", 80)
    with pytest.raises(FrozenInstanceError):
        network.egress_allow[1].port = 81
    assert read_document(policy(), records.PolicyV2, bundle).record.network.egress_allow == ()


@pytest.mark.parametrize("token", ["80", "80.0", "8e1", "0." + "0" * 5000 + "8e5002",
                                  "8" + "0" * 5000 + "e-4999", "80e+" + "0" * 5000],
                         ids=["integer", "decimal", "exponent", "fraction-compensation",
                              "integer-compensation", "long-zero-exponent"])
def test_policy_ports_accept_exact_integral_original_lexemes(bundle, token):
    doc = port_document(token)
    loaded = read_document(doc, records.PolicyV2, bundle)
    assert loaded.record.network.egress_allow[0].port == 80
    assert loaded.document is doc
    assert ('"port":' + token).encode() in loaded.document.data


@pytest.mark.parametrize("token", ["80.00000000000000000001", "79.99999999999999999999",
                                  "0", "true", "65536", "80.5", "null", '"80"', "1e-9999"])
def test_policy_ports_reject_fractional_rounding_and_invalid_values(bundle, token):
    with pytest.raises(DocumentError) as error:
        read_document(port_document(token), records.PolicyV2, bundle)
    assert error.value.diagnostics[0].source == Source("policies/writer.json", "/network/egressAllow/0/port")


@pytest.mark.parametrize("version,field,value,pointer", [
    (1, "network", None, "/authored/network"),
    (1, "network", {}, "/authored/network"),
    (1, "denyWritePaths", None, "/authored/denyWritePaths"),
    (1, "denyWritePaths", False, "/authored/denyWritePaths"),
    (1, "denyWritePaths", [False], "/authored/denyWritePaths/0"),
    (1, "requiredCapabilities", None, "/authored/requiredCapabilities"),
    (1, "requiredCapabilities", [False], "/authored/requiredCapabilities/0"),
    (1, "version", "agentsuite.policy/v2", "/authored/version"),
    (1, "mediaType", "irrelevant", "/authored/mediaType"),
    (2, "denyWritePaths", [], "/authored"),
    (2, "network", None, "/authored/network"),
    (2, "network", {}, "/authored/network"),
    (2, "network", {"egressAllow": None}, "/authored/network/egressAllow"),
    (2, "requiredCapabilities", [], "/authored/requiredCapabilities"),
])
def test_policy_profiles_are_closed_and_type_checked(bundle, version, field, value, pointer):
    kind = records.PolicyV1 if version == 1 else records.PolicyV2
    with pytest.raises(DocumentError) as error:
        read_document(policy(version, **{field: value}), kind, bundle)
    assert error.value.diagnostics[0].source.pointer == pointer


@pytest.mark.parametrize("field", ["version", "denyWritePaths", "requiredCapabilities"])
def test_policy_v1_requires_own_fields(bundle, field):
    tree = json.loads(policy(1).data)
    del tree[field]
    doc = Document.from_bytes(json.dumps(tree).encode(), Source("policy.json"))
    with pytest.raises(DocumentError) as error:
        read_document(doc, records.PolicyV1, bundle)
    assert error.value.diagnostics[0].source.pointer == "/" + field


def test_shared_policy_accepted_and_v2_refused_wire_vectors(bundle):
    vectors = [json.loads(line) for line in (ROOT / "policy/testdata/decode-cases.jsonl").read_bytes().splitlines()]
    accepted = refused_v2 = 0
    assert len(vectors) >= 190
    for vector in vectors:
        data = vector["input"].encode() if "input" in vector else bytes.fromhex(vector["inputHex"])
        if vector["valid"]:
            accepted += 1
            doc = Document.from_bytes(data, Source(vector["name"]))
            kind = records.PolicyV1 if doc.value["version"] == "agentsuite.policy/v1" else records.PolicyV2
            loaded = read_document(doc, kind, bundle)
            assert loaded.document is doc
            assert loaded.document.data == data
        elif b"agentsuite.policy/v2" in data:
            refused_v2 += 1
            with pytest.raises(ValueError):
                doc = Document.from_bytes(data, Source(vector["name"]))
                read_document(doc, records.PolicyV2, bundle)
    assert accepted == 27
    assert refused_v2 > 0


def test_policy_v2_owning_schema_runs_before_exact_port_conversion(bundle):
    doc = port_document("80.00000000000000000001")
    doc = Document.from_bytes(doc.data.replace(b'"TCP"', b'"UDP"'), doc.source)
    with pytest.raises(DocumentError) as error:
        read_document(doc, records.PolicyV2, bundle)
    assert error.value.diagnostics[0].code == "schema.const"
    assert error.value.diagnostics[0].source.pointer == "/network/egressAllow/0/protocol"
