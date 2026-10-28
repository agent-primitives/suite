"""Owned loopback registry for actual HTTP requests, never a provider service."""
from __future__ import annotations

import base64
import hashlib
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class LocalRegistry:
    def __init__(self):
        self.blobs = {}
        self.manifests = {}
        self.calls = []
        self.override = lambda method, path, headers, body: None
        self.auth = None
        self.realm = None
        self.location = None
        self.digest_headers = True
        self.password = 'fixture-password-not-a-credential'
        self.token = 'fixture-bearer-not-a-credential'
        self.base = ''

    def reply(self, method, path, headers, body):
        self.calls.append((method, path, dict(headers), body))
        override = self.override(method, path, headers, body)
        if override is not None:
            return override
        parts = urlsplit(path)
        basic = 'Basic ' + base64.b64encode(('fixture:' + self.password).encode()).decode()
        if parts.path == '/token':
            if self.auth == 'basic' and headers.get('Authorization') != basic:
                return 401, {}, b''
            return 200, {'Content-Type': 'application/json'}, json.dumps({'token': self.token}).encode()
        if self.auth and headers.get('Authorization') != (basic if self.auth == 'basic' else 'Bearer ' + self.token):
            challenge = 'Basic realm="fixture"' if self.auth == 'basic' else (
                'Bearer realm="' + (self.realm or self.base + '/token') + '",service="fixture",scope="repository:team/suite:pull,push"')
            return 401, {'WWW-Authenticate': challenge}, b''
        if method == 'POST' and parts.path.endswith('/blobs/uploads/'):
            return 202, {'Location': self.location or parts.path + 'fixture?state=keep%2Bexact'}, b''
        if method == 'PUT' and '/blobs/uploads/' in parts.path:
            digest = parse_qs(parts.query).get('digest', [''])[0]
            if digest != 'sha256:' + hashlib.sha256(body).hexdigest():
                return 400, {}, b''
            self.blobs[digest] = body
            return 201, {'Docker-Content-Digest': digest} if self.digest_headers else {}, b''
        if '/blobs/' in parts.path and method == 'HEAD':
            digest = parts.path.rsplit('/', 1)[1]
            if digest not in self.blobs:
                return 404, {}, b''
            return 200, {'Content-Length': str(len(self.blobs[digest]))}, b''
        if '/manifests/' in parts.path:
            digest = parts.path.rsplit('/', 1)[1]
            if method == 'PUT':
                if digest != 'sha256:' + hashlib.sha256(body).hexdigest():
                    return 400, {}, b''
                self.manifests[digest] = body
                return 201, {'Docker-Content-Digest': digest} if self.digest_headers else {}, b''
            if method == 'GET' and digest in self.manifests:
                return 200, {'Content-Type': 'application/vnd.oci.image.manifest.v1+json'}, self.manifests[digest]
        return 404, {}, b''


@contextmanager
def registry_server():
    registry = LocalRegistry()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def dispatch(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            status, headers, output = registry.reply(self.command, self.path, self.headers, body)
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            if 'Content-Length' not in headers:
                self.send_header('Content-Length', str(len(output)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(output)

        do_GET = do_HEAD = do_POST = do_PUT = dispatch

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    registry.base = f'http://127.0.0.1:{server.server_port}'
    thread.start()
    try:
        yield registry
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
