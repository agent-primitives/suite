"""Exercise both distribution paths without a runtime checkout dependency."""
import json
import os
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_schema_checkout_bytes_are_portable():
    for path in (ROOT / "schema").glob("*.schema.json"):
        ref = "HEAD:schema/" + path.name
        committed = subprocess.check_output(["git", "show", ref], cwd=ROOT)
        windows = subprocess.check_output(
            ["git", "-c", "core.autocrlf=true", "cat-file", "--filters", ref], cwd=ROOT
        )
        assert windows == committed, f"checkout conversion changes schema bytes: {path.name}"
        assert path.read_bytes() == committed, f"schema checkout differs from provenance: {path.name}"


def test_wheel_and_sdist_preserve_exact_offline_bundle(tmp_path):
    source = ROOT / "python"
    assert (source / "pyproject.toml").exists(), "Python build metadata missing"
    direct = tmp_path / "direct"
    rebuilt = tmp_path / "rebuilt"
    subprocess.run([sys.executable, "-m", "build", str(source), "--wheel", "--outdir", str(direct)], check=True)
    # Default build constructs a wheel from the sdist in an isolated temp tree.
    subprocess.run([sys.executable, "-m", "build", str(source), "--outdir", str(rebuilt)], check=True)
    expected = {p.name: p.read_bytes() for p in (ROOT / "schema").glob("*.schema.json")}
    provenances = []
    for directory in (direct, rebuilt):
        wheel, = directory.glob("*.whl")
        with zipfile.ZipFile(wheel) as archive:
            names = {Path(n).name for n in archive.namelist() if n.endswith(".schema.json")}
            assert names == expected.keys()
            for name, data in expected.items():
                assert archive.read("agent_suite/_schemas/" + name) == data
            provenances.append(archive.read("agent_suite/_schemas/provenance.json"))
    assert provenances[0] == provenances[1], "sdist lost source provenance"
    provenance = json.loads(provenances[0])
    assert len(provenance["schemaRevision"]) == 40
    assert set(provenance["schemas"]) == expected.keys()
    environment = tmp_path / "installed"
    venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheel, = rebuilt.glob("*.whl")
    subprocess.run([str(python), "-m", "pip", "install", str(wheel)], cwd=tmp_path, check=True)
    smoke = """
import agent_suite
from agent_suite._schema import Bundle
from agent_suite._models import Source
from agent_suite._directory import load_directory
from agent_suite._archive import load_layer
from agent_suite._oci import load_oci_layout
from agent_suite._documents import read_documents
from agent_suite._records import Agent
from pathlib import Path
import gzip
import io
assert callable(load_directory)
assert load_oci_layout(Path('layout')).source_type == 'oci-layout'
assert not load_layer(io.BytesIO(gzip.compress(b'', mtime=0))).entries
assert not hasattr(agent_suite, 'Package')
bundle = Bundle.installed()
assert len(bundle.schemas) == 15
records = read_documents(load_oci_layout(Path('layout')), bundle)
assert isinstance(records.agents[0].record, Agent)
assert records.agents[0].record.id == 'writer'
assert records.agents[0].record.instructions.source.pointer == '/instructions'
assert not hasattr(records, 'verified_root_digest')
for schema in bundle.schemas.values():
    bundle.registry.resolver(schema['$id'])
assert bundle.validate('agent.schema.json', {}, Source('agent.json'))
print('installed offline bundle: 15 exact schemas; no public loader')
"""
    from test_oci import materialize
    materialize(tmp_path / 'layout', {'layout': 'minimal-0644'})
    subprocess.run([str(python), "-I", "-c", smoke], cwd=tmp_path, check=True)
