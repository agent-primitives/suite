import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_offline_registry_resolves_all_bundled_refs():
    from agent_suite._schema import Bundle
    bundle = Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / "schema").glob("*.json")})
    assert len(bundle.schemas) == 15
    # Cross-file inference, execution, evidence and eval-case references.
    def refs(value):
        if isinstance(value, dict):
            if "$ref" in value:
                yield value["$ref"]
            for child in value.values():
                yield from refs(child)
        elif isinstance(value, list):
            for child in value:
                yield from refs(child)
    count = 0
    for schema in bundle.schemas.values():
        resolver = bundle.registry.resolver(schema["$id"])
        for ref in refs(schema):
            resolver.lookup(ref)
            count += 1
    assert count >= 191


def test_schema_diagnostics_have_source_and_json_pointer():
    from agent_suite._models import Source
    from agent_suite._schema import Bundle
    bundle = Bundle.from_bytes({"one.json": json.dumps({
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.test/one", "type": "object",
        "properties": {"a/b~c": {"type": "string"}}, "additionalProperties": False,
    }).encode()})
    result = bundle.validate("one.json", {"a/b~c": 4}, Source("agent.json"))
    assert len(result) == 1
    assert result[0].source == Source("agent.json", "/a~1b~0c")
    assert result[0].code == "schema.type"
    assert bundle.validate("one.json", {"a/b~c": "ok"}, Source("agent.json")) == []


@pytest.mark.parametrize("reference", ["$ref", "$dynamicRef"])
def test_unknown_reference_fails_closed(reference):
    from agent_suite._schema import Bundle
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.test/one", "type": "object",
        "properties": {"optional": {reference: "https://unavailable.invalid/schema"}},
    }
    with pytest.raises(ValueError, match="reference"):
        Bundle.from_bytes({"one.json": json.dumps(schema).encode()})


@pytest.mark.parametrize("constraint", [
    {"type": "integer"}, {"pattern": "^allowed$"},
    {"oneOf": [{"const": "a"}, {"const": "b"}]},
])
def test_diagnostics_do_not_copy_instance_values(constraint):
    from agent_suite._models import Source
    from agent_suite._schema import Bundle
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.test/one", **constraint,
    }
    bundle = Bundle.from_bytes({"one.json": json.dumps(schema).encode()})
    result = bundle.validate("one.json", "sample-private-value", Source("agent.json"))
    assert len(result) == 1
    assert "sample-private-value" not in result[0].message
    assert result[0].code == "schema." + next(iter(constraint))
    assert result[0].source == Source("agent.json")


def test_reference_closure_uses_nested_base_scopes_and_ignores_literal_data():
    from agent_suite._models import Source
    from agent_suite._schema import Bundle
    root = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.test/root", "type": "object",
        "$defs": {"nested": {"$id": "nested/child", "$ref": "target"}},
        "properties": {"item": {"$ref": "#/$defs/nested"}},
        "examples": [{"$ref": "https://not-a-schema.invalid/example"}],
    }
    target = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://example.test/nested/target", "type": "string",
    }
    bundle = Bundle.from_bytes({"root.json": json.dumps(root).encode(),
                               "target.json": json.dumps(target).encode()})
    assert bundle.validate("root.json", {"item": "ok"}, Source("agent.json")) == []
    assert bundle.validate("root.json", {"item": 4}, Source("agent.json"))


def test_duplicate_schema_identity_is_refused():
    from agent_suite._schema import Bundle
    schema = b'{"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"https://example.test/same"}'
    with pytest.raises(ValueError, match="duplicate"):
        Bundle.from_bytes({"a.json": schema, "b.json": schema})
