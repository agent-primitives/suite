"""Private content rules; success here is not package validation."""
import hashlib
import json
import os
import subprocess
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ORACLE_ROOT = Path(os.environ.get('AGENTSUITE_GO_ORACLE_ROOT', str(ROOT))).resolve()


def named_rows(data, key, minimum, name="name"):
    rows = data[key]
    assert isinstance(rows, list) and len(rows) >= minimum, "truncated " + key
    names = [row[name] for row in rows]
    assert all(names) and len(set(names)) == len(names), "missing/duplicate " + key
    return rows


def corpus():
    data = json.loads((ROOT / "testdata/conformance/directory-cases.json").read_bytes())
    for key, minimum in {"paths": 15, "links": 9, "collisions": 9, "retention": 7, "budgets": 5}.items():
        named_rows(data, key, minimum)
    return data


def access_corpus():
    data = json.loads((ROOT / "testdata/conformance/directory-access-cases.json").read_bytes())
    named_rows(data, "files", 3, "path")
    for case in named_rows(data, "cases", 20):
        assert case["platform"] in {"all", "posix", "windows"}, "unknown directory platform"
    return data


def accepts(function, *args):
    try:
        function(*args)
    except ValueError:
        return False
    return True


def test_shared_directory_rules():
    from agent_suite import _content
    from agent_suite._content import Content, Entry
    from agent_suite._paths import validate_link, validate_path
    data = corpus()
    assert data["limits"] == {
        "entries": _content.MAX_ENTRIES, "contentBytes": _content.MAX_CONTENT_BYTES,
        "retainedBytes": _content.MAX_RETAINED_BYTES, "jsonBytes": _content.MAX_JSON_BYTES,
        "pathBytes": 1024,
    }
    for case in data["paths"]:
        value = case.get("value")
        if value is None:
            value = bytes.fromhex(case["hex"]).decode("utf-8", "surrogateescape")
        assert accepts(validate_path, value) == case["valid"], case["name"]
    for case in data["links"]:
        assert accepts(validate_link, case["path"], case["target"]) == case["valid"], case["name"]
    for case in data["collisions"]:
        content = Content()
        content.add(Entry(case["first"]))
        assert (not accepts(content.add, Entry(case["second"]))) == case["collide"], case["name"]
    for case in data["retention"]:
        assert _content.retains(case["path"], case["size"]) == case["retained"], case["name"]
    for case in data["budgets"]:
        assert accepts(_content.add_retained, case["current"], case["size"]) == case["valid"], case["name"]


def test_private_content_metadata():
    from agent_suite._content import Content, Entry
    content = Content()
    content.add(Entry("empty.json", data=b""))
    content.add(Entry("instructions.md"))
    content.add(Entry("folder", kind="directory", mode=0o755))
    assert content.data("empty.json") == b""
    with pytest.raises(ValueError, match="retained"):
        content.data("instructions.md")
    with pytest.raises(ValueError, match="regular"):
        content.data("folder")
    with pytest.raises(ValueError, match="missing"):
        content.data("missing.json")
    with pytest.raises(ValueError, match="duplicate"):
        content.add(Entry("empty.json"))


def secure(root):
    if os.name == "nt":
        from _directory_windows_fixture import secure_fixture
        secure_fixture(root)


def test_directory_loading(tmp_path):
    from agent_suite._directory import load_directory
    secure(tmp_path)
    assert load_directory(tmp_path).entries == {}
    files = {"raw.json": b' {"x":1}\n', "empty.json": b"", "instructions.md": b"literal\r\n", "folder/payload.bin": b"a\r\nb\x1ac\x00\xff"}
    (tmp_path / "folder").mkdir()
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    secure(tmp_path)
    content = load_directory(tmp_path)
    assert content.source_type == "directory"
    assert set(content.entries) == set(files) | {"folder"}
    for name, data in files.items():
        entry = content.entries[name]
        assert (entry.path, entry.kind, entry.mode, entry.size, entry.uid, entry.gid) == (name, "file", 0o644, len(data), 0, 0)
        assert entry.digest == "sha256:" + hashlib.sha256(data).hexdigest()
        assert entry.data == (data if name.endswith(".json") else None)
    assert content.entries["folder"].kind == "directory"
    assert content.entries["folder"].mode == 0o755
    assert content.entries["folder"].size == 0
    assert content.data("empty.json") == b""


def test_directory_limits(tmp_path, monkeypatch):
    from agent_suite import _content
    from agent_suite._directory import load_directory
    for name in ("a.json", "b.json"):
        (tmp_path / name).write_bytes(b"{}")
    secure(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(_content, "MAX_ENTRIES", 1)
        with pytest.raises((ValueError, OSError), match="entr"):
            load_directory(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(_content, "MAX_CONTENT_BYTES", 3)
        with pytest.raises(ValueError, match="content.*bytes"):
            load_directory(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(_content, "MAX_RETAINED_BYTES", 3)
        with pytest.raises(ValueError, match="retained"):
            load_directory(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(_content, "MAX_JSON_BYTES", 1)
        assert all(e.data is None for e in load_directory(tmp_path).entries.values())


def test_directory_changed_file(tmp_path, monkeypatch):
    from agent_suite import _directory
    (tmp_path / "file").write_bytes(b"original")
    secure(tmp_path)
    original = _directory.Native.stat

    def replace(self, parent, name):
        observed = original(self, parent, name)
        replacement = tmp_path / "replacement"
        replacement.write_bytes(b"changed")
        if os.name == "nt":
            from _directory_windows_fixture import set_acl
            set_acl(replacement, "P(A;;FA;;;{owner})")
        replacement.replace(tmp_path / name)
        return observed

    monkeypatch.setattr(_directory.Native, "stat", replace)
    with pytest.raises(ValueError, match="changed"):
        _directory.load_directory(tmp_path)


def test_shared_directory_access(tmp_path):
    from agent_suite._directory import load_directory
    data = access_corpus()
    platform = "windows" if os.name == "nt" else "posix"
    count = 0
    for case in data["cases"]:
        if case["platform"] not in ("all", platform):
            continue
        count += 1
        root = tmp_path / case["name"]
        root.mkdir()
        for file in data["files"]:
            target = root / file["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bytes.fromhex(file["hex"]))
        secure(root)
        selected = root
        kind = case["kind"]
        target = root / case.get("path", "")
        if kind == "root-alias":
            selected = tmp_path / (case["name"] + "-alias")
            if os.name == "nt":
                from _directory_windows_fixture import junction
                junction(selected, root)
            else:
                selected.symlink_to(root, target_is_directory=True)
        elif kind == "symlink":
            target.symlink_to(case["target"])
        elif kind == "fifo":
            os.mkfifo(target, 0o600)
        elif kind in ("root-mode", "file-mode", "directory-mode"):
            target.chmod(case["mode"])
        elif kind == "acl":
            from _directory_windows_fixture import set_acl
            set_acl(root, case["dacl"], case["protected"])
        elif kind == "junction":
            from _directory_windows_fixture import junction
            junction(target, root / case["target"])
        elif kind == "inherited-owner":
            from _directory_windows_fixture import set_owner
            target = root / "inherited"
            target.mkdir()
            set_owner(target)
        elif kind != "none":
            raise AssertionError("unknown directory fixture: " + kind)
        if not case["valid"]:
            error = OSError if case["name"] == "unsupported-ace" else (OSError, ValueError)
            message = "unsupported ACE" if case["name"] == "unsupported-ace" else None
            with pytest.raises(error, match=message):
                load_directory(selected)
            continue
        content = load_directory(selected)
        for file in data["files"]:
            raw = bytes.fromhex(file["hex"])
            entry = content.entries[file["path"]]
            assert (entry.kind, entry.mode, entry.size, entry.digest, entry.uid, entry.gid) == ("file", 0o644, len(raw), "sha256:" + hashlib.sha256(raw).hexdigest(), 0, 0)
            assert entry.data == (raw if file["path"].endswith(".json") else None)
    assert count >= 8


def test_directory_corpus_guards(monkeypatch):
    original = Path.read_bytes
    for filename, loader in (("directory-cases.json", corpus), ("directory-access-cases.json", access_corpus)):
        data = json.loads((ROOT / "testdata/conformance" / filename).read_bytes())
        for key in ("paths", "links", "collisions", "retention", "budgets") if loader is corpus else ("files", "cases"):
            for rows in ([], data[key][:-1], data[key][1:] + data[key][1:2]):
                bad = {**data, key: rows}
                with monkeypatch.context() as patch:
                    patch.setattr(Path, "read_bytes", lambda path: json.dumps(bad).encode() if path.name == filename else original(path))
                    with pytest.raises(AssertionError):
                        loader()
        if loader is access_corpus:
            data["cases"][-1]["platform"] = "window"
            with monkeypatch.context() as patch:
                patch.setattr(Path, "read_bytes", lambda path: json.dumps(data).encode() if path.name == filename else original(path))
                with pytest.raises(AssertionError, match="platform"):
                    loader()


def test_windows_root_share_contract(tmp_path, monkeypatch):
    from agent_suite._directory_windows import Native
    native = object.__new__(Native)
    calls = []

    def create(*args):
        calls.append(args)
        return 42

    monkeypatch.setattr(native, "_create", create, raising=False)
    monkeypatch.setattr(native, "_adopt", lambda *args: 42)
    assert native.open_root(tmp_path) == 42
    # Go syscall.Open does not share delete on the selected root. Its relative
    # NT opens do, but that must not relax the root's Windows rename lock.
    assert calls[0][2] == 3


def test_go_casefold_differential():
    from agent_suite._casefold import fold_case
    # A new Unicode endpoint needs full-scalar verification, not a runtime refusal.
    assert unicodedata.unidata_version in {"13.0.0", "14.0.0", "15.0.0", "15.1.0", "16.0.0"}
    result = subprocess.run(
        ["go", "run", str(ORACLE_ROOT / "python/tests/testdata/fold_oracle.go")],
        cwd=ORACLE_ROOT, check=True, capture_output=True,
    )
    reference = json.loads(result.stdout)
    for scalar in range(0x110000):
        if 0xD800 <= scalar <= 0xDFFF:
            continue
        value = chr(scalar)
        assert fold_case(value) == reference.get(value, value), hex(scalar)
