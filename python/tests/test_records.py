"""Private typed snapshots retain authored bytes and precise nested locations."""
import base64
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agent_suite._json import Number
from agent_suite._models import Descriptor, Document, Platform, Source
from agent_suite._record_decode import DocumentError, read_document
from agent_suite._records import (
    Agent, Catalog, Extension, FileRef, InferenceRequirements, Located, ManifestRef,
    RawFragment, Suite, ToolProvider,
)
from agent_suite._schema import Bundle

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bundle():
    return Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / "schema").glob("*.json")})


def document(path):
    return Document.from_bytes((ROOT / "testdata" / path).read_bytes(), Source(path))


def changed(doc, **fields):
    # Preserve integer spellings in unchanged fixture fields; Number is a float.
    return Document.from_bytes(json.dumps({**json.loads(doc.data), **fields}).encode(), doc.source)


def test_typed_suite_references_are_frozen_and_located(bundle):
    doc = document("minimal/agentsuite.json")
    loaded = read_document(doc, Suite, bundle)
    suite = loaded.record
    assert loaded.document is doc
    assert isinstance(suite, Located)
    assert suite.name == "minimal"
    assert isinstance(suite.agents, tuple)
    assert isinstance(suite.agents[0], ManifestRef)
    assert isinstance(suite.agents[0].descriptor, Descriptor)
    assert suite.agents[0].source == Source(doc.source.file, "/agents/0")
    assert suite.agents[0].version == ""
    assert suite.compositions[0].platform == Platform("linux", "amd64")
    assert suite.runtime_profiles == suite.tool_provider_compositions == ()
    assert suite.build_profiles[0].source.pointer == "/buildProfiles/0"
    with pytest.raises(FrozenInstanceError):
        suite.agents[0].id = "changed"
    tree = doc.value
    tree["agents"].clear()
    assert len(doc.value["agents"]) == len(suite.agents) == 1
    assert loaded.document.data == doc.data


def test_agent_nested_records_and_optional_fields(bundle):
    doc = document("minimal/agents/writer.json")
    agent = read_document(doc, Agent, bundle).record
    assert isinstance(agent.instructions, FileRef)
    assert agent.instructions.source.pointer == "/instructions"
    assert agent.model.source.pointer == "/model"
    assert agent.model.model
    assert agent.model.capabilities is None
    assert agent.model.endpoint_env == ""
    assert agent.model.secret_refs == agent.tool_providers == agent.evals == ()
    assert agent.policy is None
    capabilities = {"api": "openai-chat-completions-v1", "contextTokens": 8192,
                    "outputTokens": 1024, "streaming": False, "toolCalling": True}
    other = read_document(changed(doc, model={"protocol": "openai", "capabilities": capabilities},
                                  invokes=[{"agent": "worker", "maxConcurrent": 2, "maxDepth": 3}]),
                          Agent, bundle).record
    assert isinstance(other.model.capabilities, InferenceRequirements)
    assert other.model.capabilities.context_tokens == 8192
    assert other.model.capabilities.streaming is False
    assert other.model.capabilities.source.pointer == "/model/capabilities"
    assert other.invokes[0].max_depth == 3
    assert other.invokes[0].source.pointer == "/invokes/0"


def test_remote_provider_is_typed_to_secret_and_credential_leaves(bundle):
    provider = read_document(document("remote-mcp/tool-provider.json"), ToolProvider, bundle).record
    assert provider.retained is True
    assert provider.variants == ()
    tool = provider.tools[0]
    assert tool.effects == ("remote-read",)
    assert tool.output_schema.source.pointer == "/tools/0/outputSchema"
    auth = tool.delegated_authorization
    assert auth.service == "search"
    assert auth.credential.binding_ref == "search-delegated-connection"
    assert auth.credential.source.pointer == "/tools/0/delegatedAuthorization/credential"
    remote = provider.remote
    assert remote.headers[0].secret_ref.key == "token"
    assert remote.headers[0].secret_ref.source.pointer == "/remote/headers/0/secretRef"
    assert remote.network[0].destination_ref == "search-mcp-egress"
    assert remote.timeouts.connect_milliseconds == 5000
    assert remote.timeouts.source.pointer == "/remote/timeouts"


def test_variants_are_explicit_raw_fragments_not_typed_claims(bundle):
    doc = document("tool-providers/kubectl-tool-provider.json")
    provider = read_document(doc, ToolProvider, bundle).record
    fragment = provider.variants[0]
    assert isinstance(fragment, RawFragment)
    assert fragment.document is doc
    assert fragment.path == ("variants", 0)
    assert fragment.source == Source(doc.source.file, "/variants/0")
    value = fragment.value
    value["files"].clear()
    assert fragment.value["files"]
    assert isinstance(fragment.value["files"][0]["mode"], Number)
    assert fragment.value["files"][0]["mode"].lexeme.isdigit()
    escaped = RawFragment(Document.from_bytes(b'{"a/b~c":[1e0]}', Source("f", "/base")),
                          ("a/b~c", 0))
    assert escaped.source == Source("f", "/base/a~1b~0c/0")
    assert escaped.value.lexeme == "1e0"


@pytest.mark.parametrize("suffix", [b"", b',"toolProviders":null', b',"toolProviders":[]'])
def test_catalog_go_empty_list_forms_preserve_raw_presence(bundle, suffix):
    data = (b'{"schemaVersion":"1.0.0-draft","mediaType":'
            b'"application/vnd.agentsuite.tool.provider.catalog.v1+json"' + suffix + b'}')
    doc = Document.from_bytes(data, Source("catalog.json"))
    assert read_document(doc, Catalog, bundle).record.tool_providers == ()
    assert doc.data == data
    assert ("toolProviders" in doc.value) == bool(suffix)


@pytest.mark.parametrize("extension", [{}, {"name": "example"}])
def test_agent_extensions_follow_go_shape_and_zero_defaults(bundle, extension):
    doc = changed(document("minimal/agents/writer.json"), extensions=[extension])
    result = read_document(doc, Agent, bundle).record.extensions[0]
    assert isinstance(result, Extension)
    assert result.critical is False and result.digest == ""
    assert result.source.pointer == "/extensions/0"


@pytest.mark.parametrize("extension,pointer", [
    ({"surprise": True}, "/extensions/0/surprise"),
    ({"critical": "false"}, "/extensions/0/critical"),
    ([], "/extensions/0"),
    (None, "/extensions/0"),
    ({"name": None}, "/extensions/0/name"),
    ({"critical": None}, "/extensions/0/critical"),
    ({"digest": None}, "/extensions/0/digest"),
])
def test_agent_open_schema_does_not_erase_go_extension_shape(bundle, extension, pointer):
    doc = changed(document("minimal/agents/writer.json"), extensions=[extension])
    with pytest.raises(DocumentError) as error:
        read_document(doc, Agent, bundle)
    assert error.value.diagnostics[0].source == Source(doc.source.file, pointer)


@pytest.mark.parametrize("lexeme", ["1.0", "1e0", "9223372036854775808"])
def test_integer_fields_require_original_integer_lexeme_and_int64(bundle, lexeme):
    doc = document("minimal/agents/writer.json")
    data = doc.data.rstrip()[:-1] + (',"invokes":[{"agent":"worker","maxConcurrent":' + lexeme +
                                   ',"maxDepth":1}]}').encode()
    with pytest.raises(DocumentError) as error:
        read_document(Document.from_bytes(data, doc.source), Agent, bundle)
    diagnostic = error.value.diagnostics[0]
    assert diagnostic.source.pointer == "/invokes/0/maxConcurrent"
    assert diagnostic.code == "document.integer"


@pytest.mark.parametrize("fields,pointer", [
    ({"surprise": 1}, "/surprise"), ({"toolProviders": {}}, "/toolProviders"),
    ({"toolProviders": [False]}, "/toolProviders/0"),
    ({"schemaVersion": "bad"}, "/schemaVersion"),
    ({"mediaType": "bad"}, "/mediaType"),
])
def test_catalog_handwritten_closed_shape_and_envelope(bundle, fields, pointer):
    doc = changed(document("minimal/tool-providers/catalog.json"), **fields)
    with pytest.raises(DocumentError) as error:
        read_document(doc, Catalog, bundle)
    assert isinstance(error.value.diagnostics, tuple)
    assert error.value.diagnostics[0].source == Source(doc.source.file, pointer)


def test_schema_is_run_before_conversion_with_unchanged_bundle(bundle):
    doc = changed(document("minimal/agents/writer.json"), description="x" * 4097,
                  extensions=[{"critical": "bad"}])
    with pytest.raises(DocumentError) as error:
        read_document(doc, Agent, bundle)
    assert error.value.diagnostics[0].code == "schema.maxLength"
    assert error.value.diagnostics[0].source.pointer == "/description"


def test_existing_shared_shape_and_string_vectors_through_decoder(bundle):
    kinds = {"suite.schema.json": Suite, "agent.schema.json": Agent,
             "tool-provider.schema.json": ToolProvider}
    cases = json.loads((ROOT / "testdata/conformance/document-shape-cases.json").read_bytes())["cases"]
    assert len(cases) == 32
    tested = 0
    for case in cases:
        if case["schema"] not in kinds:
            continue  # Other document kinds belong to later graph work.
        tested += 1
        doc = Document.from_bytes(base64.b64decode(case["bytes"]), Source(case["file"]))
        if case["valid"]:
            assert read_document(doc, kinds[case["schema"]], bundle).document is doc
        else:
            with pytest.raises(DocumentError):
                read_document(doc, kinds[case["schema"]], bundle)
    assert tested > 0
    cases = json.loads((ROOT / "testdata/conformance/string-length-cases.json").read_bytes())["cases"]
    assert len(cases) == 21
    for case in cases:
        if case["target"] == "agentDescription":
            doc = changed(document("minimal/agents/writer.json"), description=case["value"])
            kind = Agent
        else:
            kind = ToolProvider
            path = ("remote-mcp/tool-provider.json" if case["target"] == "remoteHeaderName"
                    else "tool-providers/opa-tool-provider.json")
            original = document(path)
            tree = json.loads(original.data)
            if case["target"] == "remoteHeaderName":
                owner, field = tree["remote"]["headers"][0], "name"
            elif case["target"] == "runtimeABIVersion":
                owner, field = tree["variants"][0]["runtime"], "abiVersion"
            else:
                owner = tree["variants"][0]["files"][0]
                field = "linkTarget" if case["target"] == "inventoryLinkTarget" else "component"
            if case.get("omit"):
                owner.pop(field, None)
            else:
                owner[field] = case["value"]
            doc = Document.from_bytes(json.dumps(tree).encode(), original.source)
        if case["valid"]:
            assert read_document(doc, kind, bundle).document is doc
        else:
            with pytest.raises(DocumentError):
                read_document(doc, kind, bundle)
