import { createHash } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const TAG = /^v0\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;
const FILE = /^[a-zA-Z0-9][a-zA-Z0-9._-]*\.json$/;
const HASH = /^[a-f0-9]{64}$/;
const COMMIT = /^[a-f0-9]{40}$/;
const STABLE = /^https:\/\/suite\.agent-primitives\.dev\/schema\/(v0\.(?:0|[1-9]\d*))\/([a-zA-Z0-9][a-zA-Z0-9._-]*\.json)$/;
const DRAFT = /^https:\/\/suite\.agent-primitives\.dev\/schema\/(draft)\/([a-zA-Z0-9][a-zA-Z0-9._-]*\.json)$/;
const LEGACY = /^https:\/\/kaimahi\.dev\/schemas\/agentsuite\/(?:[a-zA-Z0-9_-]+\/)*[a-zA-Z0-9][a-zA-Z0-9._-]*\.json$/;
const digest = value => createHash('sha256').update(value).digest('hex');
const assetUrl = release => `https://github.com/agent-primitives/suite/releases/download/${release}/schemas-${release}.json`;
function requireThat(ok, message) { if (!ok) throw new Error(message); }
function record(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && [Object.prototype, null].includes(Object.getPrototypeOf(value));
}
function shape(value, keys, label) {
  requireThat(record(value) && isDeepStrictEqual(Object.keys(value).sort(), keys.slice().sort()), `Invalid ${label} shape`);
}
function tag(release) {
  const match = typeof release === 'string' && TAG.exec(release);
  requireThat(match, `Invalid release tag: ${release}`);
  return { minor: `v0.${match[1]}`, patch: match[2] };
}
function identity(id) {
  requireThat(typeof id === 'string', 'Schema $id must be a string');
  const stable = STABLE.exec(id) ?? DRAFT.exec(id);
  requireThat(stable || LEGACY.test(id), `Unsupported schema $id: ${id}`);
  return stable;
}
function inventoryShape(inventory) {
  requireThat(record(inventory) && Object.keys(inventory).length > 0, 'Empty or invalid schema inventory');
  const ids = new Set();
  for (const [filename, info] of Object.entries(inventory)) {
    requireThat(FILE.test(filename), `Unsafe schema filename: ${filename}`);
    shape(info, ['id', 'sha256'], `schema ${filename}`);
    const stable = identity(info.id);
    requireThat(!stable || stable[2] === filename, `Schema $id filename mismatch: ${filename}`);
    requireThat(typeof info.sha256 === 'string' && HASH.test(info.sha256), `Invalid schema checksum: ${filename}`);
    requireThat(!ids.has(info.id), `Duplicate schema $id: ${info.id}`);
    ids.add(info.id);
  }
}
function namespace(inventory) {
  const namespaces = new Set(Object.values(inventory).map(info => identity(info.id)?.[1] ?? 'legacy'));
  requireThat(namespaces.size === 1, 'Mixed stable/legacy or stable namespaces');
  return [...namespaces][0];
}

function parseSchema(text) {
  const value = JSON.parse(text); // Establish JSON grammar before scanning key boundaries.
  const stack = [];
  for (const [token] of text.matchAll(/"(?:\\[\s\S]|[^"\\])*"|[{}\[\],]/g)) {
    const frame = stack.at(-1);
    if (token[0] === '"' && frame?.keys && frame.expectKey) {
      const key = JSON.parse(token);
      requireThat(!frame.keys.has(key), 'Duplicate JSON name in schema');
      frame.keys.add(key);
      frame.expectKey = false;
    } else if (token === '{') stack.push({ keys: new Set(), expectKey: true });
    else if (token === '[') stack.push({});
    else if (token === '}' || token === ']') stack.pop();
    else if (token === ',' && frame?.keys) frame.expectKey = true;
  }
  return value;
}

export function schemaInventory(schemaTextMap) {
  requireThat(record(schemaTextMap), 'Invalid schema text map');
  const inventory = {};
  for (const filename of Object.keys(schemaTextMap).sort()) {
    const text = schemaTextMap[filename];
    requireThat(typeof text === 'string', `Schema text must be UTF-8: ${filename}`);
    requireThat(Buffer.from(text).toString('utf8') === text, `Invalid UTF-8 schema: ${filename}`);
    const schema = parseSchema(text);
    requireThat(record(schema), `Invalid schema object: ${filename}`);
    inventory[filename] = { id: schema.$id, sha256: digest(text) };
  }
  inventoryShape(inventory);
  return inventory;
}

export function readCatalog(value) {
  const catalog = typeof value === 'string' ? JSON.parse(value) : value;
  shape(catalog, ['version', 'bundles', 'releases'], 'catalog');
  requireThat(catalog.version === 1 && Array.isArray(catalog.bundles) && record(catalog.releases), 'Invalid catalog version or collections');
  const paths = new Map();
  const releases = new Set();
  for (const entry of catalog.bundles) {
    shape(entry, ['path', 'release', 'sourceCommit', 'assetUrl', 'sha256', 'schemas'], 'bundle');
    const { minor, patch } = tag(entry.release);
    inventoryShape(entry.schemas);
    const ns = namespace(entry.schemas);
    requireThat(ns === 'legacy' ? entry.path === `archive/${entry.release}`
      : entry.path === minor && ns === minor && patch === '0', `Invalid bundle path or namespace: ${entry.path}`);
    requireThat(typeof entry.sourceCommit === 'string' && COMMIT.test(entry.sourceCommit)
      && typeof entry.sha256 === 'string' && HASH.test(entry.sha256), 'Invalid bundle commit or checksum');
    requireThat(entry.assetUrl === assetUrl(entry.release), 'Invalid canonical release asset URL');
    requireThat(!paths.has(entry.path) && !releases.has(entry.release), 'Duplicate bundle path or release');
    requireThat(catalog.releases[entry.release] === entry.path, `Unmapped bundle: ${entry.path}`);
    paths.set(entry.path, entry);
    releases.add(entry.release);
  }
  for (const [release, entryPath] of Object.entries(catalog.releases)) {
    const { minor } = tag(release);
    const entry = paths.get(entryPath);
    requireThat(entry && (entryPath.startsWith('archive/') ? release === entry.release : minor === entryPath),
      `Invalid or dangling release mapping: ${release}`);
  }
  return catalog;
}

export function checkCatalog(current, previous) {
  readCatalog(current);
  readCatalog(previous);
  for (const entry of previous.bundles) {
    requireThat(isDeepStrictEqual(current.bundles.find(candidate => candidate.path === entry.path), entry),
      `Catalog bundle deleted or mutated: ${entry.path}`);
  }
  for (const [release, entryPath] of Object.entries(previous.releases)) {
    requireThat(current.releases[release] === entryPath, `Catalog release deleted or retargeted: ${release}`);
  }
}

export function checkSchemas(schemaTextMap, catalog, { release } = {}) {
  readCatalog(catalog);
  const inventory = schemaInventory(schemaTextMap);
  const ns = namespace(inventory);
  for (const entry of catalog.bundles.filter(entry => !entry.path.startsWith('archive/'))) {
    const pinned = new Map(Object.values(entry.schemas).map(info => [info.id, info.sha256]));
    for (const info of Object.values(inventory)) {
      requireThat(!pinned.has(info.id) || pinned.get(info.id) === info.sha256, `Catalogued stable $id changed: ${info.id}`);
    }
    requireThat(ns !== entry.path || isDeepStrictEqual(inventory, entry.schemas), `Stable namespace inventory changed: ${ns}`);
  }
  if (release !== undefined) {
    const { minor, patch } = tag(release);
    requireThat(ns === 'legacy' || ns === minor, `Release/schema namespace mismatch: ${release}`);
    const entry = catalog.bundles.find(entry => entry.path === minor);
    if (patch !== '0' && (ns !== 'legacy' || entry)) {
      requireThat(entry && isDeepStrictEqual(inventory, entry.schemas), `Stable patch requires exact catalogued minor: ${minor}`);
    }
  }
}

export function createBundle(release, sourceCommit, schemaTextMap, catalog) {
  const { minor, patch } = tag(release);
  requireThat(typeof sourceCommit === 'string' && COMMIT.test(sourceCommit), 'Invalid source commit');
  checkSchemas(schemaTextMap, catalog, { release });
  const inventory = schemaInventory(schemaTextMap);
  const stable = namespace(inventory) !== 'legacy';
  const updated = structuredClone(catalog);
  if (stable && patch !== '0') {
    const entry = catalog.bundles.find(entry => entry.path === minor);
    updated.releases[release] = entry.path;
    checkCatalog(updated, catalog);
    return { asset: null, entry, catalog: updated };
  }
  const schemas = Object.fromEntries(Object.keys(inventory).map(filename => [filename, schemaTextMap[filename]]));
  const asset = Buffer.from(JSON.stringify({ version: 1, release, sourceCommit, schemas }) + '\n');
  requireThat(asset.length <= 1024 * 1024, 'Schema asset exceeds 1 MiB');
  const entry = { path: stable ? minor : `archive/${release}`, release, sourceCommit,
    assetUrl: assetUrl(release), sha256: digest(asset), schemas: inventory };
  const existing = catalog.bundles.find(candidate => candidate.path === entry.path);
  requireThat(!existing || isDeepStrictEqual(existing, entry), `Conflicting existing bundle: ${entry.path}`);
  if (!existing) updated.bundles.push(entry);
  updated.releases[release] = entry.path;
  checkCatalog(updated, catalog);
  return { asset, entry: existing ?? entry, catalog: updated };
}
const MAX_ASSET = 1024 * 1024;
async function downloadAsset(initialUrl) {
  let url = initialUrl;
  for (let redirects = 0; ; redirects++) {
    const response = await fetch(url, { redirect: 'manual', credentials: 'omit', signal: AbortSignal.timeout(30_000) });
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      await response.body?.cancel();
      requireThat(redirects < 3 && response.headers.get('location'), 'Release asset redirect limit or missing location');
      const next = new URL(response.headers.get('location'), url);
      requireThat(next.protocol === 'https:' && next.hostname === 'release-assets.githubusercontent.com'
        && !next.port && !next.username && !next.password && !next.hash, 'Unsafe release asset redirect');
      url = next.href;
      continue;
    }
    if (response.status !== 200) {
      await response.body?.cancel();
      throw new Error(`Release asset HTTP ${response.status}`);
    }
    const length = response.headers.get('content-length');
    if (length !== null && (!/^\d+$/.test(length) || Number(length) > MAX_ASSET)) {
      await response.body?.cancel();
      throw new Error('Release asset exceeds 1 MiB or invalid content-length');
    }
    const chunks = [];
    let size = 0;
    for await (const chunk of response.body ?? []) {
      size += chunk.length;
      requireThat(size <= MAX_ASSET, 'Release asset exceeds 1 MiB');
      chunks.push(Buffer.from(chunk));
    }
    return Buffer.concat(chunks);
  }
}

export async function publishCatalog(catalog, outDir, { fetchAsset = downloadAsset } = {}) {
  readCatalog(catalog);
  const verified = [];
  // Validate every pinned archive before touching the deployment tree.
  for (const entry of catalog.bundles) {
    const bytes = await fetchAsset(entry.assetUrl);
    requireThat(Buffer.isBuffer(bytes) && bytes.length <= MAX_ASSET, 'Invalid asset bytes or exceeds 1 MiB');
    requireThat(digest(bytes) === entry.sha256, `Asset checksum mismatch: ${entry.release}`);
    const archive = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
    shape(archive, ['version', 'release', 'sourceCommit', 'schemas'], 'asset');
    requireThat(archive.version === 1 && archive.release === entry.release && archive.sourceCommit === entry.sourceCommit,
      `Asset release/commit metadata mismatch: ${entry.release}`);
    requireThat(isDeepStrictEqual(schemaInventory(archive.schemas), entry.schemas), `Asset schema inventory mismatch: ${entry.release}`);
    verified.push({ entry, schemas: archive.schemas });
  }
  const root = path.join(outDir, 'schema');
  for (const { entry, schemas } of verified) {
    const target = path.join(root, entry.path);
    await mkdir(target, { recursive: true });
    for (const [filename, text] of Object.entries(schemas)) await writeFile(path.join(target, filename), text, 'utf8');
  }
  await mkdir(root, { recursive: true });
  await writeFile(path.join(root, 'catalog.json'), JSON.stringify(catalog, null, 2) + '\n');
}
