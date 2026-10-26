"""Private evaluation records retain authored presence without execution defaults."""
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


def case(assertions=None, **changes):
    value = {"schemaVersion": "1.0.0-draft", "mediaType": "application/vnd.agentsuite.eval.case.v1+json",
             "id": "case", "input": "Question?", "assertions": assertions if assertions is not None else [
                 {"id": "answer", "type": "contains", "value": "answer"}]}
    value.update(changes)
    return Document.from_bytes(json.dumps(value, indent=2).encode() + b" \n", Source("evals/writer/cases/case.json", "/snapshot"))


def index():
    descriptor = {"mediaType": "application/vnd.agentsuite.eval.case.v1+json",
                  "digest": "sha256:" + "a" * 64, "size": 12}
    return {"schemaVersion": "1.0.0-draft", "mediaType": "application/vnd.agentsuite.eval.index.v1+json",
            "agent": "writer", "limits": {"maxCases": 2, "maxCaseBytes": 4194304},
            "cases": [{"path": f"evals/writer/cases/{name}.json", "descriptor": descriptor} for name in ("z", "a")]}


def test_evaluation_index_is_frozen_ordered_and_located(bundle):
    doc = Document.from_bytes(json.dumps(index(), indent=2).encode() + b"\n", Source("evals/writer/index.json"))
    loaded = read_document(doc, records.EvaluationIndex, bundle)
    assert loaded.document is doc
    assert loaded.document.data.endswith(b"\n")
    value = loaded.record
    assert value.agent == "writer"
    assert value.schema_version == "1.0.0-draft"
    assert value.media_type == "application/vnd.agentsuite.eval.index.v1+json"
    assert isinstance(value.limits, records.EvaluationLimits)
    assert (value.limits.max_cases, value.limits.max_case_bytes) == (2, 4194304)
    assert value.limits.source.pointer == "/limits"
    assert tuple(ref.path for ref in value.cases) == ("evals/writer/cases/z.json", "evals/writer/cases/a.json")
    assert value.cases[1].source.pointer == "/cases/1"
    assert value.cases[0].descriptor.size == 12
    with pytest.raises(FrozenInstanceError):
        value.limits.max_cases = 1


def test_evaluation_assertions_preserve_every_operand_and_optional_presence(bundle):
    assertions = [
        {"id": "c", "type": "contains", "value": "answer"},
        {"id": "n", "type": "notContains", "value": "wrong", "critical": False},
        {"id": "r", "type": "regex", "pattern": "^answer$", "critical": True},
        {"id": "t", "type": "toolCalled", "tool": "lookup"},
        {"id": "nt", "type": "toolNotCalled", "tool": "delete"},
        {"id": "j", "type": "llmJudge", "rubric": "Check facts\n\tand sources", "minScore": 0,
         "judgeModel": "judge-model", "judgeVersion": "v1"},
        {"id": "future", "type": "future.check", "critical": False, "value": "opaque\noperand"},
    ]
    doc = case(assertions)
    loaded = read_document(doc, records.EvaluationCase, bundle)
    value = loaded.record
    assert loaded.document is doc
    assert loaded.document.data.endswith(b" \n")
    assert (value.id, value.input, value.runs, value.min_passes) == ("case", "Question?", None, None)
    assert value.schema_version == "1.0.0-draft"
    assert value.media_type == "application/vnd.agentsuite.eval.case.v1+json"
    assert isinstance(value.assertions, tuple)
    assert tuple(a.id for a in value.assertions) == ("c", "n", "r", "t", "nt", "j", "future")
    for i, a in enumerate(value.assertions):
        assert isinstance(a, records.EvaluationAssertion)
        assert a.source == Source(doc.source.file, f"/snapshot/assertions/{i}")
    assert value.assertions[0].critical is None
    assert value.assertions[1].critical is False
    assert value.assertions[2].critical is True
    assert value.assertions[0].value == "answer"
    assert value.assertions[1].value == "wrong"
    assert value.assertions[2].pattern == "^answer$"
    assert value.assertions[3].tool == "lookup"
    assert value.assertions[4].tool == "delete"
    judge = value.assertions[5]
    assert (judge.rubric, judge.min_score, judge.judge_model, judge.judge_version) == (
        "Check facts\n\tand sources", 0, "judge-model", "v1")
    assert (judge.value, judge.pattern, judge.tool, judge.critical) == (None, None, None, None)
    first = value.assertions[0]
    assert (first.pattern, first.tool, first.rubric, first.min_score, first.judge_model, first.judge_version) == (None,) * 6
    assert (value.assertions[6].kind, value.assertions[6].value) == ("future.check", "opaque\noperand")
    with pytest.raises(FrozenInstanceError):
        value.assertions[0].value = "changed"
    doc.value["assertions"].clear()
    assert len(value.assertions) == len(doc.value["assertions"]) == 7


@pytest.mark.parametrize("changes,expected", [({}, (None, None)), ({"runs": 3}, (3, None)),
                                             ({"runs": 3, "minPasses": 2}, (3, 2)),
                                             ({"runs": 2, "minPasses": 3}, (2, 3))])
def test_evaluation_repeats_never_materialize_execution_defaults(bundle, changes, expected):
    value = read_document(case(**changes), records.EvaluationCase, bundle).record
    assert (value.runs, value.min_passes) == expected


@pytest.mark.parametrize("field,token", [(f, t) for f in ("runs", "minPasses", "minScore", "maxCases", "maxCaseBytes")
                                       for t in ("1.0", "1e0", "1.0000000000000000001")])
def test_evaluation_integer_fields_require_original_integer_tokens(bundle, field, token):
    if field.startswith("max"):
        tree = index()
        tree["limits"][field] = "TOKEN"
        kind = records.EvaluationIndex
    elif field == "minScore":
        tree = json.loads(case([{"id": "j", "type": "llmJudge", "rubric": "Judge", "minScore": "TOKEN",
                                "judgeModel": "model", "judgeVersion": "v1"}]).data)
        kind = records.EvaluationCase
    else:
        tree = json.loads(case(runs=2, **({"minPasses": 1} if field == "minPasses" else {})).data)
        tree[field] = "TOKEN"
        kind = records.EvaluationCase
    doc = Document.from_bytes(json.dumps(tree).replace('"TOKEN"', token).encode(), Source("evaluation.json"))
    with pytest.raises(DocumentError) as error:
        read_document(doc, kind, bundle)
    diagnostic = error.value.diagnostics[0]
    assert diagnostic.code == "document.integer"
    assert diagnostic.source.pointer == ("/limits/" + field if field.startswith("max") else
                                         "/assertions/0/minScore" if field == "minScore" else "/" + field)


@pytest.mark.parametrize("field", ["runs", "minPasses"])
def test_evaluation_repeat_int64_range(bundle, field):
    tree = json.loads(case(runs=2).data)
    tree[field] = "TOKEN"
    doc = Document.from_bytes(json.dumps(tree).replace('"TOKEN"', "9223372036854775808").encode(), Source("case.json"))
    with pytest.raises(DocumentError) as error:
        read_document(doc, records.EvaluationCase, bundle)
    assert error.value.diagnostics[0].code == "document.integer"
    assert error.value.diagnostics[0].source.pointer == "/" + field


@pytest.mark.parametrize("assertion", [
    {"id": "a", "type": "contains", "value": "answer", "pattern": "x"},
    {"id": "a", "type": "contains", "value": None},
    {"id": "a", "type": "contains", "value": ""},
    {"id": "a", "type": "contains", "value": "x", "critical": None},
    {"id": "a", "type": "contains", "value": "x", "unknown": False},
    {"id": "a", "type": "regex"},
    {"id": "a", "type": "future.check", "value": "x"},
    {"id": "a", "type": "future.check", "critical": True, "value": "x"},
    {"id": "a", "type": "future.check", "critical": False, "value": "x", "tool": "x"},
])
def test_evaluation_assertion_shapes_are_schema_owned(bundle, assertion):
    with pytest.raises(DocumentError) as error:
        read_document(case([assertion]), records.EvaluationCase, bundle)
    assert error.value.diagnostics[0].code.startswith("schema.")
    assert error.value.diagnostics[0].source.pointer.startswith("/snapshot/assertions/0")


@pytest.mark.parametrize("changes", [{"runs": None}, {"minPasses": None}, {"minPasses": 1},
                                     {"assertions": []}, {"extra": False}, {"mediaType": "bad"}])
def test_evaluation_case_presence_and_envelope_are_schema_owned(bundle, changes):
    with pytest.raises(DocumentError) as error:
        read_document(case(**changes), records.EvaluationCase, bundle)
    assert error.value.diagnostics[0].code.startswith("schema.")


@pytest.mark.parametrize("field,value,pointer", [
    ("cases", None, "/cases"), ("cases", [], "/cases"),
    ("limits", None, "/limits"), ("limits", {}, "/limits"),
    ("limits", {"maxCases": True, "maxCaseBytes": 1}, "/limits/maxCases"),
    ("limits", {"maxCases": 1, "maxCaseBytes": None}, "/limits/maxCaseBytes"),
    ("agent", False, "/agent"), ("schemaVersion", "bad", "/schemaVersion"),
])
def test_evaluation_index_shape_is_schema_owned(bundle, field, value, pointer):
    tree = index()
    tree[field] = value
    doc = Document.from_bytes(json.dumps(tree).encode(), Source("index.json"))
    with pytest.raises(DocumentError) as error:
        read_document(doc, records.EvaluationIndex, bundle)
    assert error.value.diagnostics[0].code.startswith("schema.")
    assert error.value.diagnostics[0].source.pointer == pointer


def test_evaluation_schema_precedes_integer_conversion(bundle):
    doc = Document.from_bytes(case(runs=1.0, mediaType="bad").data, Source("case.json"))
    with pytest.raises(DocumentError) as error:
        read_document(doc, records.EvaluationCase, bundle)
    assert error.value.diagnostics[0].code == "schema.const"
    assert error.value.diagnostics[0].source.pointer == "/mediaType"


def test_existing_rich_evaluation_fixtures_through_private_decoder(bundle):
    root = ROOT / "testdata/rich-evaluations"
    index_path = "evals/writer/index.json"
    document = Document.from_bytes((root / index_path).read_bytes(), Source(index_path))
    loaded = read_document(document, records.EvaluationIndex, bundle)
    assert loaded.document is document
    assert tuple(ref.path for ref in loaded.record.cases) == (
        "evals/writer/cases/retrieve.json", "evals/writer/cases/summarize.json",
        "evals/writer/cases/format.json", "evals/writer/cases/offline.json")
    decoded = []
    for ref in loaded.record.cases:
        data = (root / ref.path).read_bytes()
        document = Document.from_bytes(data, Source(ref.path))
        case_loaded = read_document(document, records.EvaluationCase, bundle)
        assert case_loaded.document is document
        assert case_loaded.document.data == data
        decoded.append(case_loaded.record)
    assert tuple(c.id for c in decoded) == ("retrieve", "summarize", "format", "offline")
    assert tuple((c.runs, c.min_passes) for c in decoded) == ((None, None), (3, 2), (2, None), (None, None))
    assert tuple(tuple(a.kind for a in c.assertions) for c in decoded) == (
        ("toolCalled", "contains"), ("llmJudge", "notContains"), ("regex",), ("toolNotCalled", "contains"))
    assert decoded[1].assertions[0].min_score == 85
    assert decoded[1].assertions[1].critical is False
    assert decoded[2].assertions[0].pattern == "(?m)^source: [a-z0-9-]+$"
    assert decoded[3].assertions[0].source == Source("evals/writer/cases/offline.json", "/assertions/0")
