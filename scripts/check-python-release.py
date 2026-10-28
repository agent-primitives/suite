"""Owner-run release qualification; no network, tag creation or upload."""
import argparse
import email.parser
import hashlib
import json
import os
import re
import subprocess
import tarfile
import zipfile
from pathlib import Path


SHA = re.compile(r'[0-9a-f]{40}')
SDK_TAG = re.compile(r'python/v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)')
CONTRACT_TAG = re.compile(r'v0\.8\.(0|[1-9]\d*)')


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE)


def revision(repo, ref):
    value = git(repo, 'rev-parse', '--verify', '--end-of-options', ref+'^{commit}').decode().strip()
    if not SHA.fullmatch(value):
        raise ValueError('invalid release source revision')
    return value


def inventory(repo, commit):
    files = {}
    for path in sorted((repo/'schema').glob('*.schema.json')):
        data = path.read_bytes()
        if data != git(repo, 'show', commit+':schema/'+path.name):
            raise ValueError('schema checkout differs from tagged bytes')
        document = json.loads(data)
        identity = document['$id']
        if identity != 'https://suite.agent-primitives.dev/schema/v0.8/'+path.name:
            raise ValueError('release requires frozen v0.8 schema IDs')
        files[path.name] = data
    if not files:
        raise ValueError('release schema inventory is empty')
    return files


def distribution(path, wheel):
    if wheel:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError('duplicate distribution member')
            metadata = [n for n in names if n.endswith('.dist-info/METADATA')]
            if len(metadata) != 1:
                raise ValueError('invalid wheel metadata')
            info = archive.read(metadata[0])
            files = {n.removeprefix('agent_suite/_schemas/'): archive.read(n)
                     for n in names if n.startswith('agent_suite/_schemas/') and not n.endswith('/')}
    else:
        with tarfile.open(path, 'r:gz') as archive:
            members = archive.getmembers()
            names = [m.name for m in members]
            if len(names) != len(set(names)):
                raise ValueError('duplicate distribution member')
            metadata = [m for m in members if m.name.count('/') == 1 and m.name.endswith('/PKG-INFO')]
            if len(metadata) != 1:
                raise ValueError('invalid sdist metadata')
            stream = archive.extractfile(metadata[0])
            if stream is None:
                raise ValueError('missing sdist metadata')
            info = stream.read()
            files = {}
            for member in members:
                if '/_schema_source/' in member.name and member.isfile():
                    stream = archive.extractfile(member)
                    files[member.name.split('/_schema_source/', 1)[1]] = stream.read()
    metadata = email.parser.BytesParser().parsebytes(info)
    if metadata['Name'] != 'agent-suite':
        raise ValueError('distribution name mismatch')
    return metadata['Version'], files


def qualify(options):
    if not SDK_TAG.fullmatch(options.sdk_tag) or not CONTRACT_TAG.fullmatch(options.contract_tag):
        raise ValueError('release requires exact SDK and frozen v0.8 root tags')
    if not SHA.fullmatch(options.catalog_ref):
        raise ValueError('catalog requires a pinned main revision')
    sdk = Path(options.sdk_repo).resolve()
    contract = Path(options.contract_repo).resolve()
    catalog = Path(options.catalog_repo).resolve()
    sdk_sha = git(sdk, 'rev-parse', 'HEAD').decode().strip()
    suite_sha = git(contract, 'rev-parse', 'HEAD').decode().strip()
    if (sdk_sha != revision(catalog, 'refs/tags/'+options.sdk_tag)
            or suite_sha != revision(catalog, 'refs/tags/'+options.contract_tag)
            or git(catalog, 'rev-parse', 'HEAD').decode().strip() != options.catalog_ref):
        raise ValueError('release checkout/tag/catalog revision mismatch')
    schemas = inventory(sdk, sdk_sha)
    if schemas != inventory(contract, suite_sha):
        raise ValueError('SDK schema bytes differ from selected contract')
    rows = {name: {'id': json.loads(data)['$id'], 'sha256': hashlib.sha256(data).hexdigest()}
            for name, data in schemas.items()}
    registry = json.loads(git(catalog, 'show', options.catalog_ref+':docs/schema-catalog.json'))
    entries = [entry for entry in registry['bundles'] if entry['path'] == 'v0.8']
    if len(entries) != 1 or entries[0]['schemas'] != rows:
        raise ValueError('reviewed catalog/schema inventory mismatch')
    entry = entries[0]
    if (entry['release'] != 'v0.8.0' or entry['sourceCommit'] != revision(catalog, 'refs/tags/v0.8.0')
            or registry['releases'].get('v0.8.0') != 'v0.8'):
        raise ValueError('catalog/root tag binding mismatch')
    if Path(os.environ.get('AGENTSUITE_GO_ORACLE_ROOT', '')).resolve() != contract:
        raise ValueError('frozen contract Go oracle root mismatch')
    version = options.sdk_tag[len('python/v'):]
    provenance = {'schemaRevision': sdk_sha, 'schemas': {name: {'id': row['id'], 'digest': 'sha256:'+row['sha256']} for name, row in rows.items()}}
    expected = dict(schemas, **{'provenance.json': None})
    for path, is_wheel in ((options.wheel, True), (options.sdist, False), (options.sdist_wheel, True)):
        found_version, files = distribution(path, is_wheel)
        if found_version != version:
            raise ValueError('SDK tag/version mismatch or development version')
        if set(files) != set(expected) or any(files[name] != data for name, data in schemas.items()):
            raise ValueError('distribution schema byte inventory mismatch')
        if json.loads(files['provenance.json']) != provenance:
            raise ValueError('distribution schema provenance mismatch')
    if (not options.wheel.name.startswith('agent_suite-'+version+'-')
            or options.sdist.name != 'agent_suite-'+version+'.tar.gz'):
        raise ValueError('publication filename/version mismatch')
    distributions = {Path(path).name: file_digest(path) for path in (options.wheel, options.sdist)}
    return {'version': version, 'sdkTag': options.sdk_tag, 'sdkRevision': sdk_sha,
            'suiteTag': options.contract_tag, 'suiteRevision': suite_sha,
            'catalogRevision': options.catalog_ref, 'schemas': rows,
            'schemaAsset': {'url': entry['assetUrl'], 'sha256': entry['sha256']},
            'validatorRevision': suite_sha, 'vectorsRevision': suite_sha,
            'sdistWheelSha256': file_digest(options.sdist_wheel), 'distributions': distributions}


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while data := stream.read(128 << 10):
            digest.update(data)
    return digest.hexdigest()


def verify_artifacts(qualification, dist):
    record = json.loads(Path(qualification).read_bytes())
    expected = record['distributions']
    actual = {p.name for p in Path(dist).iterdir()}
    if actual != set(expected):
        raise ValueError('publication distribution inventory mismatch')
    for name, digest in expected.items():
        if Path(name).name != name or file_digest(Path(dist)/name) != digest:
            raise ValueError('publication artifact hash mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('qualify')
    for name in ('sdk-repo', 'contract-repo', 'catalog-repo', 'wheel', 'sdist', 'sdist-wheel', 'out'):
        check.add_argument('--'+name, type=Path, required=True)
    for name in ('sdk-tag', 'contract-tag', 'catalog-ref'):
        check.add_argument('--'+name, required=True)
    verify = commands.add_parser('verify-artifacts')
    verify.add_argument('--qualification', type=Path, required=True)
    verify.add_argument('--dist', type=Path, required=True)
    options = parser.parse_args()
    try:
        if options.command == 'qualify':
            options.out.write_text(json.dumps(qualify(options), sort_keys=True, indent=2)+'\n')
        else:
            verify_artifacts(options.qualification, options.dist)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, 'python-release: '+str(error)+'\n')


if __name__ == '__main__':
    main()
