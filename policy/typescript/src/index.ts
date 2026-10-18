// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
import { encoder, list, maxBytes, object, port, readJSON, refuse, stringValue } from './json.js';

export const schemaVersion = 'agentsuite.policy/v1';
export const schemaVersionV2 = 'agentsuite.policy/v2';
export const filesystemDenyWrite = 'filesystem/deny-write/v1';
export const networkEgressAllow = 'network/egress-allow/v1';
export interface Endpoint { address: string; protocol: 'TCP'; port: number }
export type Policy = {
  version: typeof schemaVersion;
  denyWritePaths: string[];
  requiredCapabilities: [typeof filesystemDenyWrite];
} | {
  version: typeof schemaVersionV2;
  network: { egressAllow: Endpoint[] };
  requiredCapabilities: [typeof networkEgressAllow];
};
export interface ProviderPayload {
  version: string;
  policyBytes: Uint8Array;
  policyDigest: string;
  requiredCapabilities: string[];
}

function capabilities(value: unknown, version: string): void {
  const expected = version === schemaVersion ? filesystemDenyWrite : networkEgressAllow;
  if (!Array.isArray(value) || value.length !== 1 || value[0] !== expected) {
    refuse('Incorrect required capabilities');
  }
}

/** Decode one strict policy document. Does not resolve administrative restrictions. */
export function decodePolicy(data: Uint8Array): Policy {
  const root = object(readJSON(data), ['version', 'denyWritePaths', 'network', 'requiredCapabilities']);
  const version = root.version;
  if (version !== schemaVersion && version !== schemaVersionV2) refuse('Unsupported policy version');
  capabilities(root.requiredCapabilities, version);
  if (version === schemaVersion) {
    if (Object.hasOwn(root, 'network')) refuse('Network field in v1');
    const paths = list(root.denyWritePaths).map(stringValue);
    if (paths.length === 0 || paths.length > 4096) refuse('Path list limit');
    for (const path of paths) {
      // Equivalent to path.Clean(p) == p for absolute POSIX paths, excluding root.
      if (!path.startsWith('/') || path === '/' || path.includes('\0') ||
          path.slice(1).split('/').some(part => part === '' || part === '.' || part === '..')) {
        refuse('Path must be clean and absolute, excluding root');
      }
    }
    return { version, denyWritePaths: paths, requiredCapabilities: [filesystemDenyWrite] };
  }
  if (Object.hasOwn(root, 'denyWritePaths')) refuse('Filesystem field in v2');
  const network = object(root.network, ['egressAllow']);
  const endpoints = list(network.egressAllow);
  if (endpoints.length > 4096) refuse('Endpoint list limit');
  const egressAllow = endpoints.map(value => {
    const endpoint = object(value, ['address', 'protocol', 'port']);
    const address = stringValue(endpoint.address);
    const octets = address.split('.');
    if (octets.length !== 4 || octets.some(octet => !/^(0|[1-9][0-9]{0,2})$/.test(octet) || Number(octet) > 255)) {
      refuse('Address must be a canonical IPv4 literal');
    }
    if (endpoint.protocol !== 'TCP') refuse('Protocol must be TCP');
    return { address, protocol: 'TCP' as const, port: port(endpoint.port) };
  });
  return { version, network: { egressAllow }, requiredCapabilities: [networkEgressAllow] };
}

function canonical(policy: Policy): Uint8Array {
  let text: string;
  if (policy.version === schemaVersion) {
    // Array.sort without a comparator is unsigned UTF-16 ordering, not locale/code point ordering.
    text = JSON.stringify({
      denyWritePaths: [...new Set(policy.denyWritePaths)].sort(),
      requiredCapabilities: policy.requiredCapabilities,
      version: policy.version,
    });
  } else {
    const unique = new Map<string, Endpoint>();
    for (const endpoint of policy.network.egressAllow) {
      unique.set(`${endpoint.address}:${endpoint.port}`, endpoint);
    }
    const endpoints = [...unique.values()].sort((a, b) =>
      a.address < b.address ? -1 : a.address > b.address ? 1 : a.port - b.port);
    text = JSON.stringify({
      network: { egressAllow: endpoints.map(e => ({ address: e.address, port: e.port, protocol: e.protocol })) },
      requiredCapabilities: policy.requiredCapabilities,
      version: policy.version,
    });
  }
  // The closed policy schema only has these keys and bounded integers, so explicit
  // key order plus ECMAScript string escaping suffices; no generic JCS library.
  const bytes = encoder.encode(text);
  if (bytes.length > maxBytes) refuse('Canonical byte limit');
  return bytes;
}

/** Validate and normalize authored/effective wire bytes to canonical effective bytes. */
export function canonicalize(data: Uint8Array): Uint8Array {
  return canonical(decodePolicy(data));
}

/** Hash arbitrary bytes with the policy domain and uint64 big-endian length framing. */
export async function digest(data: Uint8Array): Promise<string> {
  const domain = encoder.encode('agentsuite-effective-policy\0v1\0');
  const framed = new Uint8Array(domain.length + 8 + data.length);
  framed.set(domain);
  new DataView(framed.buffer).setBigUint64(domain.length, BigInt(data.length), false);
  framed.set(data, domain.length + 8);
  const hash = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', framed));
  return 'sha256:' + Array.from(hash, byte => byte.toString(16).padStart(2, '0')).join('');
}

/** Create a payload from validated wire bytes; does not mutate or alias the input. */
export async function payload(data: Uint8Array): Promise<ProviderPayload> {
  const policy = decodePolicy(data);
  const policyBytes = canonical(policy);
  return {
    version: policy.version, policyBytes, policyDigest: await digest(policyBytes),
    requiredCapabilities: [...policy.requiredCapabilities],
  };
}

/** Throw on invalid identity, envelope, or noncanonical bytes. No enforcement claim. */
export async function verifyPayload(value: ProviderPayload): Promise<void> {
  const version = value.version;
  if (version !== schemaVersion && version !== schemaVersionV2) refuse('Unsupported payload version');
  capabilities(value.requiredCapabilities, version);
  if (!(value.policyBytes instanceof Uint8Array)) refuse('Expected policy bytes');
  // Snapshot before the first await so caller mutation cannot change what is verified.
  const bytes = new Uint8Array(value.policyBytes);
  const expectedDigest = value.policyDigest;
  if (await digest(bytes) !== expectedDigest) refuse('Policy digest mismatch');
  const policy = decodePolicy(bytes);
  if (policy.version !== version) refuse('Payload version mismatch');
  const normalized = canonical(policy);
  if (normalized.length !== bytes.length || normalized.some((byte, i) => byte !== bytes[i])) {
    refuse('Noncanonical policy bytes');
  }
  // Each profile has exactly one capability, checked above and inside decodePolicy.
}
