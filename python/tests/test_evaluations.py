"""Ordinary stored evaluation checks; callback tests do not claim RE2 parity."""
import copy
import json
from dataclasses import FrozenInstanceError, replace

import pytest

from agent_suite._content import Entry
from agent_suite._documents import read_documents
from agent_suite._json import canonical_bytes, digest_bytes
from agent_suite._models import Source
from agent_suite._record_decode import DocumentError
from agent_suite._schema import Bundle
from test_documents import ROOT, content_fixture, rebind_agent

INDEX = "evals/writer/index.json"
CASE = "evals/writer/cases/retrieve.json"


@pytest.fixture
def bundle():
    return Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / "schema").glob("*.json")})


def store(content, path, value):
    raw = canonical_bytes(value)
    content.entries[path] = Entry(path, size=len(raw), digest=digest_bytes(raw), data=raw)
    return {"size": len(raw), "digest": digest_bytes(raw)}


def change_index(content, change):
    value = json.loads(content.data(INDEX))
    change(value)
    pin = store(content, INDEX, value)
    rebind_agent(content, lambda a: a["evals"][0]["descriptor"].update(pin))


def change_case(content, change, path=CASE):
    value = json.loads(content.data(path))
    change(value)
    pin = store(content, path, value)
    def update(index):
        next(ref for ref in index["cases"] if ref["path"] == path)["descriptor"].update(pin)
    change_index(content, update)


def read(content, bundle, valid_regex=lambda pattern: True):
    from agent_suite._evaluations import read_evaluations
    return read_evaluations(content, read_documents(content, bundle), bundle, valid_regex)


def test_evaluation_rich_fixture_order_sources_operands_and_repeats(bundle):
    content = content_fixture("rich-evaluations")
    patterns = []
    result = read(content, bundle, lambda pattern: patterns.append(pattern) is None)
    assert list(result) == ["writer"]
    evaluations = result["writer"]
    assert [c.record.id for c in evaluations.cases] == ["retrieve", "summarize", "format", "offline"]
    assert evaluations.index.document.data == content.data(INDEX)
    for case in evaluations.cases:
        assert case.document.data == content.data(case.document.source.file)
        assert case.record.source == case.document.source
        assert all(a.source.file == case.document.source.file for a in case.record.assertions)
    first, second, third, fourth = [c.record for c in evaluations.cases]
    assert (first.runs, first.min_passes) == (None, None)
    assert (second.runs, second.min_passes) == (3, 2)
    judge = second.assertions[0]
    assert (judge.kind, judge.min_score, judge.judge_model, judge.judge_version) == (
        "llmJudge", 85, "example-judge", "2026-01-15")
    assert judge.rubric.startswith("The summary preserves")
    assert second.assertions[1].critical is False
    assert patterns == [third.assertions[0].pattern]
    assert fourth.assertions
    with pytest.raises(FrozenInstanceError):
        evaluations.cases = ()


@pytest.mark.parametrize("field,value", [("runs", 0), ("runs", None), ("runs", 9223372036854775808),
                                        ("minPasses", 1), ("assertions", []), ("input", "\u0085\u00a0\u3000")])
def test_evaluation_case_presence_and_blank_input(bundle, field, value):
    content = content_fixture("rich-evaluations")
    change_case(content, lambda c: c.update({field: value}))
    with pytest.raises(DocumentError) as error:
        read(content, bundle)
    assert error.value.diagnostics[0].source.file == CASE


@pytest.mark.parametrize("runs,minimum,valid", [(1, None, True), (3, 3, True), (3, 4, False),
                                               (3, 0, False), (9007199254740991, 1, True)])
def test_evaluation_repeat_policy_preserves_presence(bundle, runs, minimum, valid):
    content = content_fixture("rich-evaluations")
    def change(case):
        case["runs"] = runs
        if minimum is not None:
            case["minPasses"] = minimum
    change_case(content, change)
    if valid:
        case = read(content, bundle)["writer"].cases[0].record
        assert (case.runs, case.min_passes) == (runs, minimum)
    else:
        with pytest.raises(DocumentError):
            read(content, bundle)


@pytest.mark.parametrize("field,value", [("input", "\u001c"), ("input", "\ufeff")])
def test_evaluation_go_trimspace_keeps_non_go_space_input(bundle, field, value):
    content = content_fixture("rich-evaluations")
    change_case(content, lambda c: c.update({field: value}))
    assert read(content, bundle)["writer"].cases[0].record.input == value


@pytest.mark.parametrize("value,valid", [("\u001c", True), ("opaque\noperand", True), ("\ufeff", True),
                                        ("\u0085\u00a0", False)])
def test_evaluation_unknown_noncritical_values_use_go_trimspace_only(bundle, value, valid):
    content = content_fixture("rich-evaluations")
    assertion = {"id": "future", "type": "future.check", "critical": False, "value": value}
    change_case(content, lambda c: c.update(assertions=[assertion]))
    if valid:
        assert read(content, bundle)["writer"].cases[0].record.assertions[0].value == value
    else:
        with pytest.raises(DocumentError):
            read(content, bundle)


@pytest.mark.parametrize("assertion", [
    {"id": "a", "type": "future.check", "value": "x"},
    {"id": "a", "type": "future.check", "critical": True, "value": "x"},
    {"id": "a", "type": "future.check\n", "critical": False, "value": "x"},
    {"id": "a", "type": "contains", "value": "a\nline"},
    {"id": "a", "type": "notContains", "value": "a\u0085line"},
    {"id": "a", "type": "toolCalled", "tool": "tool\u2028name"},
    {"id": "a", "type": "toolNotCalled", "tool": "tool\u2029name"},
    {"id": "a", "type": "contains", "value": "x", "pattern": "x"},
    {"id": "a", "type": "regex", "pattern": None},
])
def test_evaluation_known_and_unknown_assertion_contracts(bundle, assertion):
    content = content_fixture("rich-evaluations")
    change_case(content, lambda c: c.update(assertions=[assertion]))
    with pytest.raises(DocumentError) as error:
        read(content, bundle)
    assert error.value.diagnostics[0].source.file == CASE
    assert error.value.diagnostics[0].source.pointer.startswith("/assertions/0")


def judge(**changes):
    value = {"id": "judge", "type": "llmJudge", "rubric": "facts", "minScore": 50,
             "judgeModel": "model", "judgeVersion": "v1"}
    value.update(changes)
    return value


@pytest.mark.parametrize("assertion,valid", [
    ({"id": "r", "type": "regex", "pattern": "é" * 512}, True),
    ({"id": "r", "type": "regex", "pattern": "é" * 513}, False),
    ({"id": "r", "type": "regex", "pattern": "\u0085\u3000"}, False),
    (judge(rubric="é" * 2048), True), (judge(rubric="é" * 2049), False),
    (judge(rubric="Facts\n\t\u2028\u2029"), True), (judge(rubric="facts\u0001"), False),
    (judge(judgeModel="m" * 256), True), (judge(judgeModel="m" * 257), False),
    (judge(judgeVersion="é"), False), (judge(judgeVersion="v1\n"), False),
    (judge(minScore=0), True), (judge(minScore=100), True), (judge(minScore=101), False),
])
def test_evaluation_utf8_byte_bounds_and_judge_controls(bundle, assertion, valid):
    content = content_fixture("rich-evaluations")
    change_case(content, lambda c: c.update(assertions=[assertion]))
    if valid:
        a = read(content, bundle)["writer"].cases[0].record.assertions[0]
        assert a.pattern == assertion.get("pattern")
        assert a.rubric == assertion.get("rubric")
    else:
        with pytest.raises(DocumentError) as error:
            read(content, bundle)
        assert error.value.diagnostics[0].source.file == CASE


def test_evaluation_regex_callback_is_mandatory_and_refusal_is_located(bundle):
    content = content_fixture("rich-evaluations")
    change_case(content, lambda c: c.update(assertions=[{"id": "r", "type": "regex", "pattern": "sentinel"}]))
    with pytest.raises(DocumentError) as error:
        read(content, bundle, lambda pattern: pattern != "sentinel")
    assert error.value.diagnostics[0].source == Source(CASE, "/assertions/0/pattern")
    from agent_suite._evaluations import read_evaluations
    with pytest.raises(TypeError):
        read_evaluations(content, read_documents(content, bundle), bundle)


@pytest.mark.parametrize("mutation", ["case-id", "assertion-id", "case-newline", "assertion-newline", "filename", "duplicate-path"])
def test_evaluation_ids_and_reference_paths_are_unique_and_exact(bundle, mutation):
    content = content_fixture("rich-evaluations")
    if mutation == "case-id":
        change_case(content, lambda c: c.update(id="retrieve"), "evals/writer/cases/summarize.json")
    elif mutation in {"case-newline", "filename"}:
        change_case(content, lambda c: c.update(id="retrieve\n" if mutation == "case-newline" else "different"))
    elif mutation in {"assertion-id", "assertion-newline"}:
        def change(case):
            case["assertions"] = [{"id": "a", "type": "contains", "value": "x"},
                                  {"id": "a" if mutation == "assertion-id" else "b\n", "type": "contains", "value": "y"}]
        change_case(content, change)
    else:
        def duplicate(index):
            index["cases"][1] = copy.deepcopy(index["cases"][0])
            index["cases"][1]["descriptor"]["annotations"] = {"note": "different descriptor"}
        change_index(content, duplicate)
    with pytest.raises(DocumentError):
        read(content, bundle)


@pytest.mark.parametrize("field,value", [("maxCases", 3), ("maxCases", 0), ("maxCases", 129),
                                        ("maxCaseBytes", 0), ("maxCaseBytes", 4194305)])
def test_evaluation_index_limits_are_enforced(bundle, field, value):
    content = content_fixture("rich-evaluations")
    change_index(content, lambda i: i["limits"].update({field: value}))
    with pytest.raises(DocumentError) as error:
        read(content, bundle)
    assert error.value.diagnostics[0].source.file == INDEX


def test_evaluation_max_case_bytes_counts_raw_stored_bytes(bundle):
    content = content_fixture("rich-evaluations")
    maximum = max(len(content.data(ref["path"])) for ref in json.loads(content.data(INDEX))["cases"])
    change_index(content, lambda i: i["limits"].update(maxCaseBytes=maximum))
    assert len(read(content, bundle)["writer"].cases) == 4
    change_index(content, lambda i: i["limits"].update(maxCaseBytes=maximum - 1))
    with pytest.raises(DocumentError) as error:
        read(content, bundle)
    assert error.value.diagnostics[0].source == Source("evals/writer/cases/summarize.json")


@pytest.mark.parametrize("path,kind", [("evals", "file"), ("evals/other", "directory"),
    ("evals/writer/extra", "directory"), ("evals/writer/cases/nested", "directory"),
    ("evals/writer/orphan.json", "file"), ("evals/writer/cases/link.json", "symlink")])
def test_evaluation_namespace_forbids_extra_files_and_directories(bundle, path, kind):
    content = content_fixture("rich-evaluations")
    content.entries[path] = Entry(path, kind=kind)
    with pytest.raises(DocumentError) as error:
        read(content, bundle)
    assert error.value.diagnostics[0].source == Source(path)


def test_evaluation_owned_directories_and_absent_namespace(bundle):
    content = content_fixture("rich-evaluations")
    for path in ("evals", "evals/writer", "evals/writer/cases"):
        content.entries[path] = Entry(path, kind="directory")
    assert "writer" in read(content, bundle)
    content = content_fixture()
    content.entries["evals"] = Entry("evals", kind="directory")
    assert read(content, bundle) == {}
    content.entries["evals/writer"] = Entry("evals/writer", kind="directory")
    with pytest.raises(DocumentError):
        read(content, bundle)


@pytest.mark.parametrize("count,valid", [(1000, True), (1001, False)])
def test_evaluation_assertion_count_boundary(bundle, count, valid):
    content = content_fixture("rich-evaluations")
    assertions = [{"id": f"a{i}", "type": "contains", "value": "answer"} for i in range(count)]
    change_case(content, lambda c: c.update(assertions=assertions))
    if valid:
        assert len(read(content, bundle)["writer"].cases[0].record.assertions) == count
    else:
        with pytest.raises(DocumentError):
            read(content, bundle)


@pytest.mark.parametrize("target", [INDEX, CASE])
@pytest.mark.parametrize("mutation", ["size", "hash", "raw-hash", "canonical", "media", "nonregular"])
def test_evaluation_ports_check_every_pin_before_body_semantics(bundle, target, mutation):
    from agent_suite._evaluations import read_evaluations
    content = content_fixture("rich-evaluations")
    documents = read_documents(content, bundle)
    entry = content.entries[target]
    if mutation in {"size", "hash", "nonregular", "raw-hash"}:
        changes = {"size": entry.size + 1} if mutation == "size" else {
            "digest": "sha256:" + "0" * 64} if mutation == "hash" else {
            "kind": "symlink"} if mutation == "nonregular" else {
            "data": entry.data.replace(b"writer" if target == INDEX else b"retrieve",
                                       b"otherx" if target == INDEX else b"replaced")}
        content.entries[target] = replace(entry, **changes)
    elif mutation == "canonical":
        raw = json.dumps(json.loads(content.data(target)), indent=2).encode()
        content.entries[target] = replace(entry, data=raw, size=len(raw), digest=digest_bytes(raw))
        if target == CASE:
            change_index(content, lambda i: i["cases"][0]["descriptor"].update(
                size=len(raw), digest=digest_bytes(raw)))
        else:
            rebind_agent(content, lambda a: a["evals"][0]["descriptor"].update(
                size=len(raw), digest=digest_bytes(raw)))
    if mutation in {"canonical", "media"}:
        if mutation == "media":
            if target == CASE:
                change_index(content, lambda i: i["cases"][0]["descriptor"].update(mediaType="application/json"))
            else:
                rebind_agent(content, lambda a: a["evals"][0]["descriptor"].update(mediaType="application/json"))
        # Obtain the new agent without the prerequisite's own pin gate masking this port.
        from agent_suite._models import Document
        from agent_suite._record_decode import read_document
        from agent_suite._records import Agent
        agent = read_document(Document(content.data("agents/writer.json"), Source("agents/writer.json")), Agent, bundle)
        documents = replace(documents, agents=(agent,))
    with pytest.raises(DocumentError) as error:
        read_evaluations(content, documents, bundle, lambda pattern: True)
    assert error.value.diagnostics[0].code.startswith("pin.")


@pytest.mark.parametrize("mutation", ["index-owner", "index-path", "two-indices", "case-owner", "nested-case", "case-pin", "case-media"])
def test_evaluation_owner_namespace_and_pins(bundle, mutation):
    content = content_fixture("rich-evaluations")
    if mutation == "index-owner":
        change_index(content, lambda i: i.update(agent="other"))
    elif mutation in {"case-owner", "nested-case", "case-media"}:
        def change(index):
            ref = index["cases"][0]
            if mutation == "case-media":
                ref["descriptor"]["mediaType"] = "application/json"
            else:
                ref["path"] = "evals/other/cases/retrieve.json" if mutation == "case-owner" else "evals/writer/cases/nested/retrieve.json"
        change_index(content, change)
    elif mutation == "case-pin":
        content.entries[CASE] = replace(content.entries[CASE], digest="sha256:" + "0" * 64)
    else:
        documents = read_documents(content, bundle)
        agent = documents.agents[0]
        refs = agent.record.evals
        refs = (replace(refs[0], path="evals/other/index.json"),) if mutation == "index-path" else refs * 2
        documents = replace(documents, agents=(replace(agent, record=replace(agent.record, evals=refs)),))
        from agent_suite._evaluations import read_evaluations
        with pytest.raises(DocumentError):
            read_evaluations(content, documents, bundle, lambda pattern: True)
        return
    with pytest.raises(DocumentError):
        read(content, bundle)
