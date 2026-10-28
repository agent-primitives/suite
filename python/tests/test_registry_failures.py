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


@pytest.mark.parametrize('address', ['https://fixture:password@registry.test', 'https://registry.test/path', 'https://registry.test?secret=query', 'file:///path', ''])
def test_registry_invalid_origins_refuse(address):
    with pytest.raises(ValueError):
        sdk.Registry(address)
