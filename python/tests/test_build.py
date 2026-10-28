"""Exercise both distribution paths without a runtime checkout dependency."""
import json
import os
import shutil
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
    subprocess.run([str(python), "-m", "pip", "install", "--only-binary=google-re2", str(wheel)], cwd=tmp_path, check=True)
    smoke = """
import agent_suite
from agent_suite._schema import Bundle
from agent_suite._models import Source
from agent_suite._directory import load_directory
from agent_suite._archive import load_layer
from agent_suite._oci import load_oci_layout
from agent_suite._documents import read_documents
from agent_suite._graph import read_graph
from agent_suite._records import Agent, ToolProvider, ToolProviderVariant, EvaluationIndex, EvaluationCase, PolicyV1, PolicyV2
from agent_suite._capture import capture_directory, capture_oci_layout
from agent_suite._bundles import validate_bundles
from agent_suite._content import Content, Entry
from agent_suite._record_decode import read_document
from agent_suite._models import Document
import base64
import json
from pathlib import Path
import gzip
import io
assert callable(load_directory)
assert load_oci_layout(Path('layout')).source_type == 'oci-layout'
assert not load_layer(io.BytesIO(gzip.compress(b'', mtime=0))).entries
assert callable(agent_suite.Package.load)
from importlib.metadata import version
assert version('google-re2') == '1.1.20251105'
bundle = Bundle.installed()
assert len(bundle.schemas) == 15
records = read_documents(load_oci_layout(Path('layout')), bundle)
assert isinstance(records.agents[0].record, Agent)
assert records.agents[0].record.id == 'writer'
assert records.agents[0].record.instructions.source.pointer == '/instructions'
assert not hasattr(records, 'verified_root_digest')
case = json.loads(Path('bundle-case.json').read_bytes())
row = case['providers'][0]
provider = read_document(Document(base64.b64decode(row['bytes']), Source(row['file'])), ToolProvider, bundle).record
assert isinstance(provider.variants[0], ToolProviderVariant)
content = Content()
for e in case['entries']:
    content.add(Entry(e['path'], kind=e['type'], mode=e['mode'], uid=e['uid'], gid=e['gid'],
                      size=e['size'], digest=e['digest'], link_target=e['linkTarget']))
validate_bundles(content, {row['key']: provider})
assert read_graph(load_oci_layout(Path('layout')), bundle).compositions
case = json.loads(Path('graph-case.json').read_bytes())
content = Content()
for e in case['entries']:
    body = base64.b64decode(e['bytes']) if e['bytes'] is not None else None
    content.add(Entry(e['path'], kind=e['type'], mode=e['mode'], uid=e['uid'], gid=e['gid'],
                      size=e['size'], digest=e['digest'], link_target=e['linkTarget'], data=body))
parts = read_graph(content, bundle)
assert len(parts.runtime_profiles) == len(parts.compositions) == 2
assert not hasattr(parts, 'verified_root_digest')
# Installed source and cross-resource execution uniqueness must retain the fast path.
import jsonschema._utils as equality
calls = [0]
original_equal = equality.equal
def counted_equal(left, right):
    if isinstance(left, dict) and isinstance(right, dict) and 'environment' in left and 'environment' in right:
        calls[0] += 1
    return original_equal(left, right)
equality.equal = counted_equal
profile = parts.build_profiles[0].document.value
profile['execution'] = dict(kind='http-v1', protocol='openai-chat-v1', port=8080, healthPath='/healthz',
    inputs=[dict(name='input'+str(i), environment='INPUT_'+str(i), secret=False) for i in range(256)])
assert not bundle.validate('build-profile.schema.json', profile, Source('installed.json'))
assert calls[0] <= 512
profile['execution']['inputs'].append(dict(profile['execution']['inputs'][0]))
assert [d.code for d in bundle.validate('build-profile.schema.json', profile, Source('installed.json'))] == ['schema.uniqueItems']
equality.equal = original_equal
for schema in bundle.schemas.values():
    bundle.registry.resolver(schema['$id'])
assert bundle.validate('agent.schema.json', {}, Source('agent.json'))
# Both distribution paths exercise the public complete reader with the REAL
# native backend, full authored evaluations and no runtime checkout dependency.
import shutil
from agent_suite import Package, CaseView, PolicyV2
public_directory = Package.load('rich-directory')
public_oci = Package.load('rich-layout')
assert public_directory.root_digest == public_oci.root_digest
assert public_directory.artifact_digest is None
assert public_oci.artifact_digest and public_oci.artifact_digest != public_oci.root_digest
# Full writing needs the unretained executable payload while its source exists.
# Only read/validate/literal access is promised after source removal.
from agent_suite import canonical_bytes, digest, variant_digest, oci_manifest_digest
for package_index, package in enumerate((public_directory,public_oci)):
    destination = Path('writer-output')
    if package_index == 1:
        unchanged = package.write_oci(destination/'original-oci')
        with Package.load(unchanged) as copied:
            assert copied.artifact_digest == package.artifact_digest
    before = package.root_digest
    package.set_instructions('writer', 'Installed writer round trip.')
    assert package.root_digest != before and package.validate() == ()
    assert digest(package.suite.document.value) == package.root_digest
    assert canonical_bytes({}) == b'{}'
    assert variant_digest({'variantDigest':'old'}) == digest({'variantDigest':''})
    for method in ('write_directory','write_oci'):
        path = getattr(package,method)(destination/(str(package_index)+'-'+method))
        with Package.load(path) as output:
            assert output.root_digest == package.root_digest and output.validate() == ()
            assert b''.join(output.agents['writer'].instructions.content.iter_bytes()) == b'Installed writer round trip.'
            if method == 'write_oci':
                import json
                selected = json.loads((path/'index.json').read_bytes())['manifests'][0]['digest']
                assert oci_manifest_digest((path/'blobs/sha256'/selected[7:]).read_bytes()) == output.artifact_digest
shutil.rmtree('rich-directory')
shutil.rmtree('rich-layout')
for package in (public_directory,public_oci):
    with package:
        agent = package.agents['writer']
        assert agent.evaluations is not None and len(agent.evaluations.cases) == 4
        assert isinstance(agent.policy.declaration,PolicyV2)
        kinds = set()
        for case in agent.evaluations.cases:
            assert isinstance(case,CaseView)
            for assertion in case.assertions:
                kinds.add(assertion.kind)
                assert assertion.source.file == case.source.file
        assert {'contains','notContains','regex','toolCalled','toolNotCalled','llmJudge'} <= kinds
        assert b''.join(agent.instructions.content.iter_bytes())
        for provider in package.tool_providers.values():
            for tool in provider.tools:
                assert b''.join(tool.input_schema.content.iter_bytes())
        assert package.validate() == ()
    assert package.root_digest and package.agents['writer'].declaration.id == 'writer'
# Keep all earlier private snapshot/record qualification too.

from agent_suite._json import digest_bytes
for path, loader, capture in [(Path('directory'),load_directory,capture_directory),
                               (Path('layout'),load_oci_layout,capture_oci_layout)]:
    content = loader(path)
    documents = read_documents(content,bundle)
    ref = documents.agents[0].record.instructions
    with capture(path,content,documents) as snapshot:
        shutil.rmtree(path)
        data = b''.join(snapshot.get(ref).iter_bytes())
        assert len(data) == ref.descriptor.size and digest_bytes(data) == ref.descriptor.digest
    assert snapshot.closed
for filename,kind in [('eval-index.json',EvaluationIndex),('eval-case.json',EvaluationCase),
                      ('policy.json',PolicyV2)]:
    document = Document(Path(filename).read_bytes(),Source(filename))
    assert read_document(document,kind,bundle).document.data == document.data
filesystem = Document(b'{"version":"agentsuite.policy/v1","denyWritePaths":["/data"],"requiredCapabilities":["filesystem/deny-write/v1"]}',Source('filesystem.json'))
assert read_document(filesystem,PolicyV1,bundle).record.deny_write_paths == ('/data',)
network = Document(b'{"version":"agentsuite.policy/v2","network":{"egressAllow":[]},"requiredCapabilities":["network/egress-allow/v1"]}',Source('network.json'))
assert read_document(network,PolicyV2,bundle).record.network.egress_allow == ()
print('installed offline bundle: 15 exact schemas; complete public reader; native RE2; source-independent snapshots')
"""
    cases = json.loads((ROOT / 'testdata/conformance/bundle-cases.json').read_bytes())['cases']
    baseline = next(c for c in cases if c['name'] == 'baseline-directory')
    (tmp_path / 'bundle-case.json').write_text(json.dumps(baseline), encoding='utf-8')
    graph_cases = json.loads((ROOT / 'testdata/conformance/graph-cases.json').read_bytes())['cases']
    graph_case = next(c for c in graph_cases if c['name'] == 'runtime-two-profiles')
    (tmp_path / 'graph-case.json').write_text(json.dumps(graph_case), encoding='utf-8')
    from test_oci import materialize
    for source_name,target_name in [('evals/writer/index.json','eval-index.json'),
                                    ('evals/writer/cases/retrieve.json','eval-case.json'),
                                    ('policies/writer.json','policy.json')]:
        shutil.copyfile(ROOT/'testdata/rich-evaluations'/source_name,tmp_path/target_name)
    for wheel in [wheel, next(direct.glob('*.whl'))]:
        subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--force-reinstall', str(wheel)],
                       cwd=tmp_path, check=True)
        materialize(tmp_path / 'layout', {'layout': 'minimal-0644'})
        directory = tmp_path/'directory'
        shutil.copytree(ROOT/'testdata/minimal',directory)
        if os.name == 'nt':
            from _directory_windows_fixture import secure_fixture
            secure_fixture(directory)
        rich = tmp_path/'rich-directory'
        shutil.copytree(ROOT/'testdata/rich-evaluations',rich)
        if os.name == 'nt':
            secure_fixture(rich)
        from test_capture import packed_fixture
        from agent_suite._directory import load_directory
        from agent_suite._graph import read_graph
        from agent_suite._schema import Bundle
        content = load_directory(rich)
        bundle = Bundle.from_bytes({p.name:p.read_bytes() for p in (ROOT/'schema').glob('*.json')})
        read_graph(content,bundle)
        # Author archive modes from the portable inventory, not host stat modes
        # (Windows host files commonly report 0666 regardless of bundle intent).
        packed_fixture(rich,tmp_path/'rich-layout',{path:e.mode for path,e in content.entries.items()})
        output_parent = tmp_path/'writer-output'
        output_parent.mkdir(exist_ok=True)
        if os.name == 'nt':
            secure_fixture(output_parent)
        subprocess.run([str(python), "-I", "-c", smoke], cwd=tmp_path, check=True)
        shutil.rmtree(output_parent)
