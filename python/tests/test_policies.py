"""Ordinary authored policy validation, not effective policy or enforcement."""
import json
from dataclasses import replace

import pytest

from agent_suite._content import Entry
from agent_suite._documents import read_documents
from agent_suite._json import canonical_bytes, digest_bytes
from agent_suite._models import Source
from agent_suite._record_decode import DocumentError
from agent_suite._records import PolicyV1, PolicyV2
from agent_suite._schema import Bundle
from test_documents import ROOT, content_fixture, rebind_agent
from test_policy_records import policy


@pytest.fixture
def bundle():
    return Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / "schema").glob("*.json")})


def bind_policy(content, value, profile=2, raw=None):
    path = "policies/writer.json"
    raw = canonical_bytes(value) if raw is None else raw
    content.entries[path] = Entry(path, size=len(raw), digest=digest_bytes(raw), data=raw)
    ref = {"path": path, "descriptor": {"mediaType": f"application/vnd.agentsuite.policy.v{profile}+json",
                                       "size": len(raw), "digest": digest_bytes(raw)}}
    rebind_agent(content, lambda a: a.update(policy=ref))


def read(content, bundle):
    from agent_suite._policies import read_policies
    return read_policies(content, read_documents(content, bundle), bundle)


def test_policy_rich_fixture_retains_authored_order_and_source(bundle):
    content = content_fixture("rich-evaluations")
    loaded = read(content, bundle)["writer"]
    assert isinstance(loaded.record, PolicyV2)
    assert loaded.document.data == (ROOT / "testdata/rich-evaluations/policies/writer.json").read_bytes()
    endpoints = loaded.record.network.egress_allow
    assert [(e.address, e.port) for e in endpoints] == [("10.0.0.2", 80), ("9.0.0.1", 443)]
    assert endpoints[1].source == Source("policies/writer.json", "/network/egressAllow/1")


@pytest.mark.parametrize("profile", [1, 2])
def test_policy_empty_network_and_v1_duplicates_are_not_normalized(bundle, profile):
    content = content_fixture()
    bind_policy(content, json.loads(policy(profile).data), profile)
    loaded = read(content, bundle)["writer"]
    if profile == 1:
        assert isinstance(loaded.record, PolicyV1)
        assert loaded.record.deny_write_paths == ("/z", "/a", "/z")
    else:
        assert loaded.record.network.egress_allow == ()


@pytest.mark.parametrize("path", ["", "/", "relative", "/a/", "/a/./b", "/a/../b", "//a", "/a//b", "/a\x00b"])
def test_policy_v1_rejects_unclean_paths_at_body_source(bundle, path):
    content = content_fixture()
    bind_policy(content, json.loads(policy(1, denyWritePaths=[path]).data), 1)
    with pytest.raises(DocumentError) as error:
        read(content, bundle)
    assert error.value.diagnostics[0].source == Source("policies/writer.json", "/denyWritePaths/0")


def test_policy_posix_backslash_and_network_duplicates_are_authored(bundle):
    content = content_fixture()
    bind_policy(content, json.loads(policy(1, denyWritePaths=["/a\\b"]).data), 1)
    assert read(content, bundle)["writer"].record.deny_write_paths == ("/a\\b",)
    endpoint = {"address": "192.0.2.1", "protocol": "TCP", "port": 80}
    bind_policy(content, json.loads(policy(network={"egressAllow": [endpoint, endpoint]}).data))
    assert [e.port for e in read(content, bundle)["writer"].record.network.egress_allow] == [80, 80]


@pytest.mark.parametrize("address", ["192.168.001.1", "::ffff:192.0.2.1", "::1", "192.0.2.1/32", "192.0.2.1 ", "example.com"])
def test_policy_network_requires_canonical_ipv4(bundle, address):
    content = content_fixture()
    value = json.loads(policy(network={"egressAllow": [{"address": address, "protocol": "TCP", "port": 80}]}).data)
    bind_policy(content, value)
    with pytest.raises(DocumentError) as error:
        read(content, bundle)
    assert error.value.diagnostics[0].source == Source("policies/writer.json", "/network/egressAllow/0/address")


@pytest.mark.parametrize("profile,caps", [(1, []), (1, ["network/egress-allow/v1"]),
                                         (2, ["filesystem/deny-write/v1"]), (2, ["network/egress-allow/v1"] * 2)])
def test_policy_capabilities_are_exact_singleton(bundle, profile, caps):
    content = content_fixture()
    bind_policy(content, json.loads(policy(profile, requiredCapabilities=caps).data), profile)
    with pytest.raises(DocumentError) as error:
        read(content, bundle)
    assert error.value.diagnostics[0].source.file == "policies/writer.json"
    assert error.value.diagnostics[0].source.pointer.startswith("/requiredCapabilities")


@pytest.mark.parametrize("path,kind", [("policies", "file"), ("policies/orphan.json", "file"),
                                      ("policies/extra", "directory"), ("policies/other.json", "symlink")])
def test_policy_namespace_rejects_unreferenced_and_nonregular_entries(bundle, path, kind):
    content = content_fixture()
    content.entries[path] = Entry(path, kind=kind)
    with pytest.raises(DocumentError) as error:
        read(content, bundle)
    assert error.value.diagnostics[0].source == Source(path)


def test_policy_namespace_allows_only_root_directory_without_policy(bundle):
    content = content_fixture()
    content.entries["policies"] = Entry("policies", kind="directory")
    content.entries["policies-other"] = Entry("policies-other", kind="directory")
    assert read(content, bundle) == {}


def test_policy_owner_and_supported_media_are_bound(bundle):
    # Exercise this port independently of read_documents pinning prerequisites.
    content = content_fixture("rich-evaluations")
    documents = read_documents(content, bundle)
    agent = documents.agents[0]
    ref = replace(agent.record.policy, path="policies/other.json")
    documents = replace(documents, agents=(replace(agent, record=replace(agent.record, policy=ref)),))
    from agent_suite._policies import read_policies
    with pytest.raises(DocumentError) as error:
        read_policies(content, documents, bundle)
    assert error.value.diagnostics[0].source == Source("agents/writer.json", "/policy/path")


@pytest.mark.parametrize("mutation", ["hash", "size", "canonical", "version", "media", "nonregular"])
def test_policy_pins_and_profile_mapping_are_not_bypassed(bundle, mutation):
    content = content_fixture("rich-evaluations")
    documents = read_documents(content, bundle)
    path = "policies/writer.json"
    if mutation in {"hash", "size", "nonregular"}:
        entry = content.entries[path]
        content.entries[path] = replace(entry, **({"digest": "sha256:" + "0" * 64} if mutation == "hash" else
                                                  {"size": entry.size + 1} if mutation == "size" else {"kind": "directory"}))
    elif mutation == "canonical":
        value = json.loads(content.data(path))
        bind_policy(content, value, raw=json.dumps(value, indent=2).encode())
        # Use the newly pinned agent without running the prerequisite canonical gate.
        from agent_suite._models import Document
        from agent_suite._record_decode import read_document
        from agent_suite._records import Agent
        agent = read_document(Document(content.data("agents/writer.json"), Source("agents/writer.json")), Agent, bundle)
        documents = replace(documents, agents=(agent,))
    else:
        agent = documents.agents[0]
        ref = agent.record.policy
        ref = replace(ref, descriptor=replace(ref.descriptor, media_type=(
            "application/vnd.agentsuite.policy.v1+json" if mutation == "version" else "application/json")))
        documents = replace(documents, agents=(replace(agent, record=replace(agent.record, policy=ref)),))
    from agent_suite._policies import read_policies
    with pytest.raises(DocumentError):
        read_policies(content, documents, bundle)


@pytest.mark.parametrize("profile,count,valid", [(1, 0, False), (1, 4096, True), (1, 4097, False),
                                                (2, 4096, True), (2, 4097, False)])
def test_policy_profile_collection_bounds(bundle, profile, count, valid):
    content = content_fixture()
    changes = {"denyWritePaths": ["/a"] * count} if profile == 1 else {
        "network": {"egressAllow": [{"address": "192.0.2.1", "protocol": "TCP", "port": 80}] * count}}
    bind_policy(content, json.loads(policy(profile, **changes).data), profile)
    if valid:
        record = read(content, bundle)["writer"].record
        assert len(record.deny_write_paths if profile == 1 else record.network.egress_allow) == count
    else:
        with pytest.raises(DocumentError):
            read(content, bundle)


def test_shared_policy_all_wire_vectors(bundle):
    from agent_suite._models import Document,Source
    from agent_suite._policies import _validate
    from agent_suite._record_decode import read_document
    from agent_suite._records import PolicyV1,PolicyV2
    vectors = [json.loads(line) for line in (ROOT/'policy/testdata/decode-cases.jsonl').read_bytes().splitlines()]
    assert len(vectors) == len({v['name'] for v in vectors}) == 190
    assert sum(v['valid'] for v in vectors) == 27
    for vector in vectors:
        raw = vector['input'].encode() if 'input' in vector else bytes.fromhex(vector['inputHex'])
        try:
            document = Document.from_bytes(raw,Source(vector['name']))
            kind = PolicyV1 if document.value.get('version')=='agentsuite.policy/v1' else PolicyV2
            loaded = read_document(document,kind,bundle)
            _validate(loaded.record)
            accepted = True
        except ValueError:
            accepted = False
        assert accepted is vector['valid'],vector['name']


def test_policy_shared_accepted_decode_vectors_pass_ordinary_semantics(bundle):
    from agent_suite._policies import read_policies
    vectors = [json.loads(line) for line in (ROOT / "policy/testdata/decode-cases.jsonl").read_bytes().splitlines()]
    for vector in vectors:
        if not vector["valid"]:
            continue
        value = json.loads(vector["input"] if "input" in vector else bytes.fromhex(vector["inputHex"]))
        profile = 1 if value["version"].endswith("/v1") else 2
        content = content_fixture()
        bind_policy(content, value, profile)
        assert "writer" in read_policies(content, read_documents(content, bundle), bundle), vector["name"]
