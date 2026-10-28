"""Private request/auth handling for one digest publication, not a general client."""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import BinaryIO
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import parse_http_list, parse_keqv_list

import requests
from requests.auth import _basic_auth_str

from ._json import MAX_BYTES


def origin(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
        if (parsed.scheme not in ('http', 'https') or not host or parsed.username is not None
                or parsed.password is not None or parsed.fragment or any(ord(c) <= 32 for c in url)):
            raise ValueError
        # Bind credentials to the same IDNA/URL authority Requests will send.
        prepared = requests.PreparedRequest()
        prepared.prepare_url(url, None)
        if not isinstance(prepared.url, str):
            raise ValueError
        host = urlsplit(prepared.url).hostname
        if not host:
            raise ValueError
        authority = '[' + host + ']' if ':' in host else host
        if port is not None:
            if not 1 <= port <= 65535:
                raise ValueError
            if port != (443 if parsed.scheme == 'https' else 80):
                authority += ':' + str(port)
        return parsed.scheme + '://' + authority
    except (ValueError, UnicodeError, AttributeError, requests.RequestException):
        raise ValueError('invalid registry HTTP origin or location') from None


def location(base: str, value: str) -> str:
    target = urljoin(base, value)
    target_origin = origin(target)
    if urlsplit(base).scheme == 'https' and urlsplit(target_origin).scheme != 'https':
        raise ValueError('registry location downgrades HTTPS')
    return target


def read_response(response: requests.Response) -> bytes:
    data = bytearray()
    for chunk in response.iter_content(128 << 10):
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise ValueError('registry response exceeds JSON byte limit')
    return bytes(data)


class HTTP:
    def __init__(self, base: str, credentials: Mapping[str, tuple[str, str]], timeout: float):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('registry timeout must be positive and finite')
        self.base = base
        self.timeout = timeout
        self.credentials = credentials
        self.authorization = ''
        self.session = requests.Session()
        self.session.trust_env = False

    def close(self) -> None:
        self.session.close()

    def request(self, method: str, url: str, stage: str, *, body: BinaryIO | bytes | None = None,
                headers: Mapping[str, str] | None = None, authenticate: bool = True) -> requests.Response:
        current = url
        fields = dict(headers or {})
        initial_origin = origin(url)
        supplied = fields.pop('Authorization', '')
        negotiated = False
        redirects = 0
        while True:
            current_origin = origin(current)
            fields.pop('Authorization', None)
            if authenticate and current_origin == self.base and self.authorization:
                fields['Authorization'] = self.authorization
            elif supplied and current_origin == initial_origin:
                fields['Authorization'] = supplied
            if body is not None and not isinstance(body, bytes):
                body.seek(0)
            self.session.cookies.clear()
            try:
                response = self.session.request(method, current, data=body, headers=fields,
                                                allow_redirects=False, timeout=self.timeout, stream=True)
            except requests.RequestException:
                raise ValueError('registry ' + stage + ' request failed') from None
            if response.status_code == 401 and authenticate and current_origin == self.base and not negotiated:
                challenge = response.headers.get('WWW-Authenticate', '')
                response.close()
                self.authorization = self._authenticate(challenge)
                negotiated = True
                continue
            if response.status_code in (307, 308):
                value = self.session.get_redirect_target(response)
                response.close()
                if not value or redirects == 3:
                    raise ValueError('registry ' + stage + ' redirect failed') from None
                current = location(current, value)
                if origin(current) != current_origin:
                    supplied = ''
                redirects += 1
                continue
            return response

    def _authenticate(self, challenge: str) -> str:
        challenges: list[tuple[str, list[str]]] = []
        for item in parse_http_list(challenge):
            parts = item.split(None, 1)
            if len(parts) == 2 and '=' not in parts[0] and not parts[1].lstrip().startswith('='):
                challenges.append((parts[0].lower(), [parts[1]]))
            elif challenges:
                challenges[-1][1].append(item)
            else:
                raise ValueError('invalid registry authentication challenge') from None
        scheme, parameters = next((item for item in challenges if item[0] == 'bearer'),
                                  challenges[0] if challenges else ('', []))
        if scheme == 'basic':
            pair = self.credentials.get(self.base)
            if pair is None:
                raise ValueError('registry credentials required') from None
            return _basic_auth_str(*pair)
        if scheme != 'bearer':
            raise ValueError('registry authentication challenge is unsupported') from None
        fields = {}
        for item in parameters:
            key, separator, value = item.partition('=')
            key = key.strip().lower()
            if not separator or key in fields:
                raise ValueError('invalid registry Bearer challenge') from None
            parsed = parse_keqv_list([key + '=' + value.strip()])
            fields[key] = next(iter(parsed.values()))
        realm = fields.get('realm', '')
        if not realm:
            raise ValueError('registry Bearer realm missing') from None
        target = location(self.base + '/', realm)
        parsed_url = urlsplit(target)
        query = urlencode([(key, fields[key]) for key in ('service', 'scope') if key in fields])
        target = urlunsplit(parsed_url._replace(query=parsed_url.query + ('&' if parsed_url.query and query else '') + query))
        headers = {}
        pair = self.credentials.get(origin(target))
        if pair is not None:
            headers['Authorization'] = _basic_auth_str(*pair)
        with self.request('GET', target, 'token', headers=headers, authenticate=False) as response:
            require(response, 200, 'token')
            import json
            try:
                document = json.loads(read_response(response))
                token = document.get('token') or document.get('access_token')
                if not isinstance(token, str) or not token or any(ord(c) <= 32 for c in token):
                    raise ValueError
            except (ValueError, AttributeError, TypeError):
                raise ValueError('invalid registry token response') from None
        return 'Bearer ' + token


def require(response: requests.Response, status: int, stage: str, digest: str = '') -> None:
    if response.status_code != status:
        raise ValueError(f'registry {stage} failed (HTTP {response.status_code})') from None
    if digest and response.headers.get('Docker-Content-Digest', digest) != digest:
        raise ValueError('registry ' + stage + ' digest mismatch') from None
