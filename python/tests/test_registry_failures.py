import io
from contextlib import contextmanager

import pytest
import agent_suite as sdk

from _registry_fixture import registry_server
from test_registry import layout
from test_package import api


@pytest.mark.parametrize('challenge', [
    'Bearer realm="{base}/token",realm="{base}/other"',
    'Bearer realm="{base}/token",broken',
    'Bearer service="fixture"',
    'Bearer realm="ftp://invalid.test/token"',
    'Unknown realm="fixture"',
])
def test_registry_malformed_challenges_refuse_safely(layout, api, challenge):
    with registry_server() as remote:
        remote.override = lambda *args: (401, {'WWW-Authenticate': challenge.format(base=remote.base)}, b'')
        with pytest.raises(ValueError):
            sdk.Registry(remote.base).publish(layout, 'team/suite')
        assert len(remote.calls) == 1


def test_registry_selects_bearer_from_multiple_challenges(layout, api):
    with registry_server() as remote:
        remote.auth = 'bearer'

        def reply(method, path, headers, body):
            if not path.startswith('/token') and 'Authorization' not in headers:
                challenge = f'Basic realm="fixture", Bearer realm="{remote.base}/token",service="fixture",scope="repository:team/suite:pull,push"'
                return 401, {'WWW-Authenticate': challenge}, b''
            return None

        remote.override = reply
        assert sdk.Registry(remote.base).publish(layout, 'team/suite')
        assert len(remote.manifests) == 1


def test_registry_bearer_parameters_allow_optional_whitespace(layout, api):
    with registry_server() as remote:
        remote.auth = 'bearer'

        def reply(method, path, headers, body):
            if not path.startswith('/token') and 'Authorization' not in headers:
                return 401, {'WWW-Authenticate': f'Bearer realm = "{remote.base}/token", service = "fixture", scope = "repository:team/suite:pull,push"'}, b''
            if path.startswith('/token'):
                from urllib.parse import parse_qs, urlsplit
                assert parse_qs(urlsplit(path).query) == {
                    'service': ['fixture'], 'scope': ['repository:team/suite:pull,push']}
            return None

        remote.override = reply
        sdk.Registry(remote.base).publish(layout, 'team/suite')
        assert len(remote.manifests) == 1


@pytest.mark.parametrize('body', [b'[]', b'{}', b'{"token":null}', b'{"token":"bad token"}', b'not-json'])
def test_registry_malformed_tokens_refuse_safely(layout, api, body):
    with registry_server() as remote:
        remote.auth = 'bearer'
        remote.override = lambda method, path, *args: (200, {}, body) if path.startswith('/token') else None
        with pytest.raises(ValueError, match='token'):
            sdk.Registry(remote.base).publish(layout, 'team/suite')
        assert not remote.blobs and not remote.manifests


def test_registry_snapshot_rechecks_bytes_before_http(layout, api, monkeypatch):
    from agent_suite import _registry
    original = _registry._open_blob

    @contextmanager
    def changed(root, descriptor):
        with original(root, descriptor) as source:
            yield io.BytesIO(b'changed' + source.read())

    monkeypatch.setattr(_registry, '_open_blob', changed)
    with registry_server() as remote:
        with pytest.raises(ValueError, match='snapshot'):
            sdk.Registry(remote.base).publish(layout, 'team/suite')
        assert remote.calls == []


def test_registry_does_not_discover_netrc_or_cookies(layout, api, tmp_path, monkeypatch):
    netrc = tmp_path/'netrc'
    netrc.write_text('machine 127.0.0.1 login fixture password fake-netrc-password\n')
    monkeypatch.setenv('NETRC', str(netrc))
    with registry_server() as remote:
        remote.override = lambda *args: (404, {'Set-Cookie': 'fixture=cookie; Path=/'}, b'') if args[0] == 'HEAD' else None
        sdk.Registry(remote.base).publish(layout, 'team/suite')
        assert all('Cookie' not in call[2] and 'Authorization' not in call[2] for call in remote.calls)


@pytest.mark.parametrize('fail', [False, True])
def test_registry_releases_streams_and_session(layout, api, monkeypatch, fail):
    from agent_suite import _registry
    original = _registry.tempfile.TemporaryFile
    streams = []
    closed = []
    original_close = _registry.HTTP.close

    def temporary(*args, **kwargs):
        stream = original(*args, **kwargs)
        streams.append(stream)
        return stream

    def close(session):
        closed.append(session)
        original_close(session)

    monkeypatch.setattr(_registry.tempfile, 'TemporaryFile', temporary)
    monkeypatch.setattr(_registry.HTTP, 'close', close)
    with registry_server() as remote:
        if fail:
            remote.override = lambda *args: (500, {}, b'')
            with pytest.raises(ValueError):
                sdk.Registry(remote.base).publish(layout, 'team/suite')
        else:
            sdk.Registry(remote.base).publish(layout, 'team/suite')
    assert len(closed) == 1 and len(streams) >= 2
    assert all(stream.closed for stream in streams)


@pytest.mark.parametrize('redirect', [False, True])
def test_registry_idna_transport_origin_binds_credentials(layout, api, monkeypatch, redirect):
    import socket
    from urllib.parse import urlsplit
    real_dns = socket.getaddrinfo

    def loopback_dns(host, port, *args, **kwargs):
        assert host in ('127.0.0.1', 'fass.test', 'xn--fa-hia.test')
        return real_dns('127.0.0.1', port, *args, **kwargs)

    monkeypatch.setattr(socket, 'getaddrinfo', loopback_dns)
    with registry_server() as remote, registry_server() as issuer:
        port = urlsplit(issuer.base).port
        allowed = f'http://fass.test:{port}'
        other = f'http://faß.test:{port}/token'
        remote.auth = 'bearer'
        remote.realm = allowed + '/token' if redirect else other
        if redirect:
            # HTTP headers carry Latin-1; Requests recovers UTF-8 Location bytes.
            issuer.override = lambda method, path, headers, body: (
                307, {'Location': other.encode('utf-8').decode('latin-1')}, b''
            ) if headers['Host'] == f'fass.test:{port}' else None
        sdk.Registry(remote.base, credentials={allowed: ('fixture', issuer.password)}).publish(layout, 'team/suite')
        forbidden = [c for c in issuer.calls if c[2]['Host'] == f'xn--fa-hia.test:{port}']
        assert len(forbidden) == 1
        assert all('Authorization' not in c[2] for c in forbidden)
        if redirect:
            assert issuer.calls[0][2]['Authorization'].startswith('Basic ')


@pytest.mark.parametrize('stage', ['basic', 'realm-basic', 'bearer-token'])
def test_registry_unicode_auth_failures_are_redacted(layout, api, stage):
    import json
    secret = 'fixture-secret-\u1200-end'
    with registry_server() as remote, registry_server() as issuer:
        remote.auth = 'basic' if stage == 'basic' else 'bearer'
        credentials = {remote.base: ('fixture', secret)} if stage == 'basic' else {}
        if stage == 'realm-basic':
            remote.realm = issuer.base + '/token'
            credentials[issuer.base] = ('fixture', secret)
        if stage == 'bearer-token':
            remote.override = lambda method, path, *args: (
                200, {}, json.dumps({'token': secret}).encode()
            ) if path.startswith('/token') else None
        with pytest.raises(ValueError) as caught:
            sdk.Registry(remote.base, credentials=credentials).publish(layout, 'team/suite')
        assert secret not in str(caught.value) + repr(caught.value)
        assert not isinstance(caught.value, UnicodeError)
        assert caught.value.__suppress_context__
        assert not remote.blobs and not remote.manifests


@pytest.mark.parametrize('address', ['https://fixture:password@registry.test', 'https://registry.test/path', 'https://registry.test?secret=query', 'file:///path', ''])
def test_registry_invalid_origins_refuse(address):
    with pytest.raises(ValueError):
        sdk.Registry(address)
