import hashlib
import json
from urllib.parse import urlsplit

import pytest
import agent_suite as sdk

from _registry_fixture import registry_server
from test_capture import extracted, secure
from test_package import api


@pytest.fixture
def layout(tmp_path, api):
    secure(tmp_path)
    root, _ = extracted(tmp_path)
    with api.Package.load(root) as package:
        return package.write_oci(tmp_path/'layout')


def test_registry_publish_preserves_manifest_and_blobs(layout, api):
    manifest = json.loads((layout/'index.json').read_bytes())['manifests'][0]
    digest = manifest['digest']
    raw = (layout/'blobs/sha256'/digest[7:]).read_bytes()
    document = json.loads(raw)
    with registry_server() as remote:
        reference = sdk.Registry(origin=remote.base).publish(layout, 'team/suite')
        assert reference == urlsplit(remote.base).netloc + '/team/suite@' + digest
        assert remote.manifests[digest] == raw
        for item in [document['config'], *document['layers']]:
            assert remote.blobs[item['digest']] == (layout/'blobs/sha256'/item['digest'][7:]).read_bytes()
        writes = [call for call in remote.calls if call[0] == 'PUT']
        assert len(writes) == 3
        assert '/manifests/' in writes[-1][1]
        assert all('/blobs/uploads/' in call[1] for call in writes[:-1])
        assert remote.calls[-1][0] == 'GET'
        assert all('Authorization' not in call[2] for call in remote.calls)


def test_registry_repeat_push_and_missing_optional_headers(layout, api):
    with registry_server() as remote:
        remote.digest_headers = False
        client = sdk.Registry(remote.base)
        first = client.publish(layout, 'team/suite')
        remote.calls.clear()
        assert client.publish(layout, 'team/suite') == first
        assert [c[0] for c in remote.calls] == ['HEAD', 'HEAD', 'PUT', 'GET']


@pytest.mark.parametrize('auth', ['basic', 'bearer'])
def test_registry_basic_and_bearer_credentials_are_origin_bound(layout, api, auth):
    with registry_server() as remote, registry_server() as issuer:
        remote.auth = auth
        issuer.auth = 'basic'
        remote.realm = issuer.base + '/token'
        credentials = {remote.base: ('fixture', remote.password), issuer.base: ('fixture', issuer.password)}
        reference = sdk.Registry(remote.base, credentials=credentials).publish(layout, 'team/suite')
        assert reference.endswith(next(iter(remote.manifests)))
        if auth == 'bearer':
            assert issuer.calls and all(c[1].startswith('/token?') for c in issuer.calls)
            assert all(c[2].get('Authorization', '').startswith('Basic ') for c in issuer.calls)
            assert all(not c[2].get('Authorization', '').startswith('Basic ') for c in remote.calls)
        else:
            assert not issuer.calls
        assert credentials[remote.base] == ('fixture', remote.password)


def test_registry_bearer_realm_does_not_inherit_registry_password(layout, api):
    with registry_server() as remote, registry_server() as issuer:
        remote.auth = 'bearer'
        remote.realm = issuer.base + '/token'
        sdk.Registry(remote.base, credentials={remote.base: ('fixture', remote.password)}).publish(layout, 'team/suite')
        assert issuer.calls
        assert all('Authorization' not in c[2] for c in issuer.calls)


def test_registry_upload_queries_and_redirects_preserve_bytes(layout, api):
    with registry_server() as remote, registry_server() as storage:
        remote.auth = 'basic'
        remote.location = '/redirect?state=keep%2Bexact'

        def reply(method, path, headers, body):
            if path.startswith('/redirect?'):
                assert 'state=keep%2Bexact' in path
                assert 'digest=sha256%3A' in path or 'digest=sha256:' in path
                return 307, {'Location': storage.base + path.replace('/redirect?', '/v2/team/suite/blobs/uploads/fixture?')}, b''
            return None

        remote.override = reply
        sdk.Registry(remote.base, credentials={remote.base: ('fixture', remote.password)}).publish(layout, 'team/suite')
        assert len(storage.blobs) == 2
        assert all('Authorization' not in c[2] for c in storage.calls)
        for digest, data in storage.blobs.items():
            assert digest == 'sha256:' + hashlib.sha256(data).hexdigest()


def test_registry_auth_replay_rewinds_body(layout, api):
    with registry_server() as remote:
        first = []

        def reply(method, path, headers, body):
            if method == 'PUT' and '/uploads/' in path and not first:
                first.append(body)
                remote.auth = 'bearer'
                return 401, {'WWW-Authenticate': f'Bearer realm="{remote.base}/token",service="fixture",scope="repository:team/suite:pull,push"'}, b''
            return None

        remote.override = reply
        sdk.Registry(remote.base).publish(layout, 'team/suite')
        assert first and first[0] in remote.blobs.values()


@pytest.mark.parametrize('invalid', ['directory', 'corrupt'])
def test_registry_refuses_before_network_on_invalid_or_changed_layout(layout, api, invalid):
    if invalid == 'directory':
        (layout/'oci-layout').unlink()
    else:
        manifest = json.loads((layout/'index.json').read_bytes())['manifests'][0]
        (layout/'blobs/sha256'/manifest['digest'][7:]).write_bytes(b'changed')
    with registry_server() as remote:
        with pytest.raises(ValueError):
            sdk.Registry(remote.base).publish(layout, 'team/suite')
        assert remote.calls == []


def test_registry_snapshots_outlive_source(layout, api):
    import shutil
    with registry_server() as remote:
        removed = []

        def reply(method, path, headers, body):
            if not removed:
                shutil.rmtree(layout)
                removed.append(True)
            return None

        remote.override = reply
        reference = sdk.Registry(remote.base).publish(layout, 'team/suite')
        assert reference.endswith(next(iter(remote.manifests)))
        assert len(remote.blobs) == 2 and not layout.exists()


@pytest.mark.parametrize('failure', ['manifest-digest', 'digest-header', 'head-size', 'final-response'])
def test_registry_uncertain_or_mismatched_remote_never_returns_reference(layout, api, failure):
    with registry_server() as remote:
        def reply(method, path, headers, body):
            if failure == 'manifest-digest' and method == 'GET' and '/manifests/' in path:
                return 200, {}, b'{}'
            if failure == 'digest-header' and method == 'PUT':
                return 201, {'Docker-Content-Digest': 'sha256:' + '0'*64}, b''
            if failure == 'head-size' and method == 'HEAD':
                return 200, {'Content-Length': '123'}, b''
            if failure == 'final-response' and method == 'PUT' and '/manifests/' in path:
                remote.manifests[path.rsplit('/', 1)[1]] = body
                return 503, {}, b'no response certainty'
            return None
        remote.override = reply
        with pytest.raises(ValueError):
            sdk.Registry(remote.base).publish(layout, 'team/suite')
        remote.override = lambda *args: None
        assert sdk.Registry(remote.base).publish(layout, 'team/suite').endswith(next(iter(remote.manifests)))


def test_registry_errors_and_repr_redact_secrets(layout, api):
    with registry_server() as remote:
        client = sdk.Registry(remote.base, credentials={remote.base: ('fixture', remote.password)})
        remote.override = lambda *args: (500, {}, remote.password.encode())
        with pytest.raises(ValueError) as caught:
            client.publish(layout, 'team/suite')
        assert remote.password not in str(caught.value) + repr(client)
        assert '500' in str(caught.value)
        assert caught.value.__suppress_context__


@pytest.mark.parametrize('repository', ['', '../suite', 'Team/suite', 'team/suite:tag', 'team//suite', 'a'*256])
def test_registry_validates_target_and_closes_resources(layout, api, repository):
    with registry_server() as remote:
        with pytest.raises(ValueError):
            sdk.Registry(remote.base).publish(layout, repository)
        assert remote.calls == []
