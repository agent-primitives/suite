import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { readCatalog, checkCatalog, schemaInventory, checkSchemas, createBundle, publishCatalog } from './schema-bundles.mjs';

const empty = () => ({ version: 1, bundles: [], releases: {} });
const commit = 'a'.repeat(40);
const hash = value => createHash('sha256').update(value).digest('hex');
const schema = (id, extra = {}) => JSON.stringify({ $id: id, type: 'object', ...extra }) + '\n';
const stable = (minor = 2) => ({ 'agent.schema.json': schema(`https://suite.agent-primitives.dev/schema/v0.${minor}/agent.schema.json`) });
const legacy = () => ({ 'agent.schema.json': schema('https://kaimahi.dev/schemas/agentsuite/agent.schema.json') });
const clone = value => structuredClone(value);

test('reads an empty catalog from JSON without changing its content', () => {
  assert.deepEqual(readCatalog('{"version":1,"bundles":[],"releases":{}}'), empty());
});

// Independent external-data fixtures keep validation tests separate from the packer.
function fixture(release = 'v0.2.0', texts = stable(), entryPath = 'v0.2') {
  const asset = Buffer.from(JSON.stringify({ version: 1, release, sourceCommit: commit, schemas: texts }) + '\n');
  const entry = { path: entryPath, release, sourceCommit: commit,
    assetUrl: `https://github.com/agent-primitives/suite/releases/download/${release}/schemas-${release}.json`,
    sha256: hash(asset), schemas: Object.fromEntries(Object.entries(texts).map(([name, text]) =>
      [name, { id: JSON.parse(text).$id, sha256: hash(text) }])) };
  return { asset, entry, catalog: { version: 1, bundles: [entry], releases: { [release]: entryPath } } };
}

test('inventory records exact UTF-8 bytes and IDs, independent of filename order', () => {
  const texts = { 'z.json': schema('https://kaimahi.dev/schemas/agentsuite/z.json'), ...stable() };
  assert.deepEqual(schemaInventory(texts), {
    'agent.schema.json': { id: 'https://suite.agent-primitives.dev/schema/v0.2/agent.schema.json', sha256: hash(texts['agent.schema.json']) },
    'z.json': { id: 'https://kaimahi.dev/schemas/agentsuite/z.json', sha256: hash(texts['z.json']) },
  });
  assert.notEqual(schemaInventory(stable())['agent.schema.json'].sha256,
    schemaInventory({ 'agent.schema.json': stable()['agent.schema.json'] + ' ' })['agent.schema.json'].sha256);
});

test('catalog accepts stable patch mappings and archive-scoped legacy reused IDs', () => {
  const first = fixture();
  first.catalog.releases['v0.2.1'] = 'v0.2';
  const old1 = fixture('v0.1.0', legacy(), 'archive/v0.1.0');
  const old2 = fixture('v0.1.1', { 'agent.schema.json': schema(JSON.parse(legacy()['agent.schema.json']).$id, { title: 'changed' }) }, 'archive/v0.1.1');
  const catalog = { version: 1, bundles: [first.entry, old1.entry, old2.entry],
    releases: { ...first.catalog.releases, ...old1.catalog.releases, ...old2.catalog.releases } };
  assert.deepEqual(readCatalog(catalog), catalog);
  assert.doesNotThrow(() => checkCatalog(catalog, old1.catalog));
});

test('catalog rejects malformed external shapes, paths, tags, IDs, and asset URLs', () => {
  const mutations = [
    c => { c.version = 2; }, c => { c.extra = true; }, c => { c.bundles = {}; }, c => { c.releases = []; },
    c => { c.bundles[0].path = '../v0.2'; }, c => { c.bundles[0].path = '/v0.2'; },
    c => { c.bundles[0].release = 'v0.02.0'; }, c => { c.bundles[0].release = 'v1.2.0'; },
    c => { c.bundles[0].sourceCommit = 'a'.repeat(39); }, c => { c.bundles[0].sha256 = 'g'.repeat(64); },
    c => { c.bundles[0].sourceCommit = ['a'.repeat(40)]; },
    c => { c.bundles[0].sha256 = ['a'.repeat(64)]; },
    c => { c.bundles[0].schemas['agent.schema.json'].sha256 = ['a'.repeat(64)]; },
    c => { delete c.bundles[0].schemas; }, c => { c.bundles[0].schemas = {}; },
    c => { c.bundles[0].schemas['../escape.json'] = c.bundles[0].schemas['agent.schema.json']; },
    c => { c.bundles[0].schemas['agent.schema.json'].sha256 = 'short'; },
    c => { c.bundles[0].schemas['agent.schema.json'].id = 'https://suite.agent-primitives.dev/schema/draft/agent.schema.json'; },
    c => { c.bundles[0].schemas['agent.schema.json'].id = 'https://evil.test/schema/v0.2/agent.schema.json'; },
    c => { c.bundles[0].schemas['agent.schema.json'].id = 'https://suite.agent-primitives.dev/schema/v0.3/agent.schema.json'; },
    c => { c.bundles[0].assetUrl = c.bundles[0].assetUrl.replace('https:', 'http:'); },
    c => { c.bundles[0].assetUrl = c.bundles[0].assetUrl.replace('github.com', 'user:secret@github.com'); },
    c => { c.bundles[0].assetUrl += '?token=secret'; },
    c => { c.bundles[0].assetUrl = 'https://evil.test/asset.json'; },
    c => { c.bundles.push(clone(c.bundles[0])); },
    c => { c.releases['v0.3.0'] = 'v0.2'; }, c => { c.releases['v0.2.1'] = 'v0.9'; },
    c => { delete c.releases['v0.2.0']; },
  ];
  for (const mutate of mutations) {
    const catalog = fixture().catalog;
    mutate(catalog);
    assert.throws(() => readCatalog(catalog), undefined, mutate.toString());
  }
  for (const texts of [{}, { '../x.json': '{}' }, { 'x.json': 'not json' }, { 'x.json': '{}' },
    { 'x.json': schema('https://kaimahi.dev/schemas/agentsuite/../x.json') },
    { 'x.json': schema('https://kaimahi.dev/schemas/agentsuite/x.json#fragment') }]) {
    assert.throws(() => schemaInventory(texts));
  }
});

test('append-only checks reject deletion, entry mutation, and release retargeting', () => {
  const previous = fixture().catalog;
  const old = fixture('v0.1.0', legacy(), 'archive/v0.1.0');
  const current = { version: 1, bundles: [...previous.bundles, old.entry],
    releases: { ...previous.releases, ...old.catalog.releases } };
  assert.doesNotThrow(() => checkCatalog(current, previous));
  assert.throws(() => checkCatalog(empty(), previous));
  for (const mutate of [c => { c.bundles[0].sha256 = 'b'.repeat(64); },
    c => { c.bundles[0].schemas['agent.schema.json'].sha256 = 'b'.repeat(64); },
    c => { c.bundles[0].sourceCommit = 'b'.repeat(40); },
    c => { c.releases['v0.2.1'] = 'archive/v0.1.0'; }]) {
    const next = clone(current);
    mutate(next);
    assert.throws(() => checkCatalog(next, previous));
  }
  const patched = clone(previous);
  patched.releases['v0.2.1'] = 'v0.2';
  assert.throws(() => checkCatalog(previous, patched));
});

test('packer preserves original text, canonical metadata, and deterministic filename order', () => {
  const texts = { 'z.json': schema('https://suite.agent-primitives.dev/schema/v0.2/z.json', { title: 'é' }), ...stable() };
  const result = createBundle('v0.2.0', commit, texts, empty());
  assert.ok(Buffer.isBuffer(result.asset));
  assert.deepEqual(JSON.parse(result.asset), { version: 1, release: 'v0.2.0', sourceCommit: commit, schemas: texts });
  assert.deepEqual(result.entry, { path: 'v0.2', release: 'v0.2.0', sourceCommit: commit,
    assetUrl: 'https://github.com/agent-primitives/suite/releases/download/v0.2.0/schemas-v0.2.0.json',
    sha256: hash(result.asset), schemas: schemaInventory(texts) });
  assert.deepEqual(result.catalog, { version: 1, bundles: [result.entry], releases: { 'v0.2.0': 'v0.2' } });
  assert.deepEqual(createBundle('v0.2.0', commit, Object.fromEntries(Object.entries(texts).reverse()), empty()).asset, result.asset);
  assert.throws(() => createBundle('v0.2.0', 'bad', texts, empty()));
  assert.throws(() => createBundle('v0.02.0', commit, texts, empty()));
});

test('stable patches reuse the original bundle and append only a release mapping', () => {
  const baseline = fixture().catalog;
  const before = clone(baseline);
  const result = createBundle('v0.2.4', 'b'.repeat(40), stable(), baseline);
  assert.equal(result.asset, null);
  assert.deepEqual(result.entry, baseline.bundles[0]);
  assert.deepEqual(result.catalog, { ...baseline, releases: { 'v0.2.0': 'v0.2', 'v0.2.4': 'v0.2' } });
  assert.deepEqual(baseline, before);
  assert.doesNotThrow(() => checkSchemas(stable(), baseline, { release: 'v0.2.4' }));
  assert.throws(() => createBundle('v0.2.4', commit, stable(), empty()));
  for (const texts of [
    { 'agent.schema.json': stable()['agent.schema.json'] + ' ' },
    { ...stable(), 'more.json': schema('https://suite.agent-primitives.dev/schema/v0.2/more.json') },
    { 'replacement.json': schema('https://suite.agent-primitives.dev/schema/v0.2/replacement.json') },
    {}, legacy(),
  ]) {
    assert.throws(() => checkSchemas(texts, baseline, { release: 'v0.2.4' }));
    assert.throws(() => createBundle('v0.2.4', commit, texts, baseline));
  }
});

test('stable namespace contracts protect content, IDs, additions and removals on main', () => {
  const baseline = fixture().catalog;
  assert.doesNotThrow(() => checkSchemas(stable(), baseline));
  assert.doesNotThrow(() => checkSchemas(stable(3), baseline));
  for (const texts of [
    { 'agent.schema.json': schema('https://suite.agent-primitives.dev/schema/v0.2/agent.schema.json', { title: 'changed' }) },
    { 'other.json': schema('https://suite.agent-primitives.dev/schema/v0.2/other.json') },
    { ...stable(), 'extra.json': schema('https://suite.agent-primitives.dev/schema/v0.2/extra.json') },
    { 'agent.schema.json': schema('https://suite.agent-primitives.dev/schema/v0.3/agent.schema.json'), 'old.json': stable()['agent.schema.json'] },
  ]) assert.throws(() => checkSchemas(texts, baseline));
});

test('refuses draft, mismatched, unknown, mixed, and colliding release identities', () => {
  for (const texts of [
    { 'agent.schema.json': schema('https://suite.agent-primitives.dev/schema/draft/agent.schema.json') },
    { 'agent.schema.json': schema('https://evil.test/agent.schema.json') }, stable(3),
    { ...stable(), 'old.json': schema('https://kaimahi.dev/schemas/agentsuite/old.json') },
    { ...stable(), 'other.json': schema('https://suite.agent-primitives.dev/schema/v0.3/other.json') },
  ]) assert.throws(() => createBundle('v0.2.0', commit, texts, empty()));
  const existing = createBundle('v0.2.0', commit, stable(), empty());
  assert.throws(() => createBundle('v0.2.0', 'b'.repeat(40), stable(), existing.catalog));
});

test('main accepts draft schemas while release checks, bundles and catalogs refuse them', () => {
  const texts = { 'agent.schema.json': schema('https://suite.agent-primitives.dev/schema/draft/agent.schema.json') };
  const catalog = fixture().catalog;
  assert.doesNotThrow(() => checkSchemas(texts, catalog));
  assert.throws(() => checkSchemas(texts, catalog, { release: 'v0.3.0' }));
  assert.throws(() => createBundle('v0.3.0', commit, texts, catalog));
  catalog.bundles[0].schemas['agent.schema.json'].id = 'https://suite.agent-primitives.dev/schema/draft/agent.schema.json';
  assert.throws(() => readCatalog(catalog));
});

test('legacy archives allow changed reused IDs without global stable-ID aliases', () => {
  const first = createBundle('v0.1.0', commit, legacy(), empty());
  const changed = { 'agent.schema.json': schema(JSON.parse(legacy()['agent.schema.json']).$id, { title: 'new' }) };
  assert.doesNotThrow(() => checkSchemas(changed, first.catalog, { release: 'v0.1.1' }));
  const next = createBundle('v0.1.1', commit, changed, first.catalog);
  assert.equal(next.entry.path, 'archive/v0.1.1');
  assert.equal(next.catalog.bundles.length, 2);
  assert.ok(Buffer.isBuffer(next.asset));
});

async function directory(t) {
  const dir = await mkdtemp(path.join(tmpdir(), 'suite-bundles-'));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return dir;
}
function twoBundles() {
  const first = fixture('v0.1.0', legacy(), 'archive/v0.1.0');
  const second = fixture();
  return { first, second, catalog: { version: 1, bundles: [first.entry, second.entry],
    releases: { ...first.catalog.releases, ...second.catalog.releases } } };
}

test('fresh and repeated deployments retain both pinned bundles and preserve flat main files', async t => {
  const { first, second, catalog } = twoBundles();
  const assets = new Map([[first.entry.assetUrl, first.asset], [second.entry.assetUrl, second.asset]]);
  for (let deployment = 0; deployment < 2; deployment++) {
    const dir = await directory(t);
    await mkdir(path.join(dir, 'schema'));
    await writeFile(path.join(dir, 'schema', 'agent.schema.json'), 'main bytes');
    for (let repeat = 0; repeat < 2; repeat++) {
      await publishCatalog(catalog, dir, { fetchAsset: async url => assets.get(url) });
      assert.equal(await readFile(path.join(dir, 'schema/archive/v0.1.0/agent.schema.json'), 'utf8'), legacy()['agent.schema.json']);
      assert.equal(await readFile(path.join(dir, 'schema/v0.2/agent.schema.json'), 'utf8'), stable()['agent.schema.json']);
      assert.equal(await readFile(path.join(dir, 'schema/agent.schema.json'), 'utf8'), 'main bytes');
      assert.deepEqual(JSON.parse(await readFile(path.join(dir, 'schema/catalog.json'), 'utf8')), catalog);
    }
  }
});

test('all archives validate before any writes on network, checksum, metadata or inventory failure', async t => {
  const scenarios = [
    { error: new Error('missing asset HTTP 404') }, { error: new Error('connection reset') },
    { bytes: Buffer.from('checksum mismatch') }, { bytes: Buffer.alloc(1024 * 1024 + 1), pin: true },
    { bytes: Buffer.from([0xff]), pin: true }, { bytes: Buffer.from('not JSON'), pin: true },
    ...[
      a => { a.version = 2; }, a => { a.release = 'v0.3.0'; }, a => { a.sourceCommit = 'b'.repeat(40); },
      a => { a.extra = true; }, a => { delete a.schemas['agent.schema.json']; },
      a => { a.schemas['extra.json'] = schema('https://suite.agent-primitives.dev/schema/v0.2/extra.json'); },
      a => { a.schemas['agent.schema.json'] += ' '; },
      a => { a.schemas['agent.schema.json'] = schema('https://suite.agent-primitives.dev/schema/v0.3/agent.schema.json'); },
      a => { a.schemas['../escape.json'] = a.schemas['agent.schema.json']; },
    ].map(mutate => ({ mutate, pin: true })),
  ];
  for (const scenario of scenarios) {
    const { first, second, catalog } = twoBundles();
    let bytes = scenario.bytes ?? second.asset;
    if (scenario.mutate) {
      const archive = JSON.parse(bytes);
      scenario.mutate(archive);
      bytes = Buffer.from(JSON.stringify(archive));
    }
    if (scenario.pin) second.entry.sha256 = hash(bytes);
    const dir = await directory(t);
    await assert.rejects(publishCatalog(catalog, dir, { fetchAsset: async url => {
      if (url === first.entry.assetUrl) return first.asset;
      if (scenario.error) throw scenario.error;
      return bytes;
    } }));
    assert.deepEqual(await readdir(dir), [], `partial writes: ${JSON.stringify(scenario)}`);
  }
});

test('empty catalog publishes its manifest without fetching', async t => {
  const dir = await directory(t);
  await publishCatalog(empty(), dir, { fetchAsset: async () => { throw new Error('unexpected fetch'); } });
  assert.deepEqual(JSON.parse(await readFile(path.join(dir, 'schema/catalog.json'), 'utf8')), empty());
});

test('default HTTP downloader rejects errors, oversized bodies and unsafe or excessive redirects', async t => {
  const bundle = fixture();
  const replies = [
    () => new Response('missing', { status: 404 }),
    () => new Response(bundle.asset, { headers: { 'content-length': String(1024 * 1024 + 1) } }),
    () => new Response(Buffer.alloc(1024 * 1024 + 1)),
    ...['http://release-assets.githubusercontent.com/a', 'https://evil.test/a',
      'https://user:secret@release-assets.githubusercontent.com/a', 'https://release-assets.githubusercontent.com:444/a',
      'https://github.com/agent-primitives/suite/other', 'https://release-assets.githubusercontent.com/a']
      .map(location => () => new Response(null, { status: 302, headers: { location } })),
  ];
  for (const reply of replies) {
    const mock = t.mock.method(globalThis, 'fetch', async () => reply());
    const dir = await directory(t);
    await assert.rejects(publishCatalog(bundle.catalog, dir));
    assert.deepEqual(await readdir(dir), []);
    mock.mock.restore();
  }
});

test('default downloader follows credential-free HTTPS release-assets redirects', async t => {
  const bundle = fixture();
  const target = 'https://release-assets.githubusercontent.com/github-production-release-asset/test?signature=ok';
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (options.redirect !== 'manual' || options.credentials !== 'omit') return new Response('unsafe', { status: 403 });
    if (url === bundle.entry.assetUrl) return new Response(null, { status: 302, headers: { location: target } });
    if (url === target) return new Response(bundle.asset);
    throw new Error('Unexpected URL');
  });
  const dir = await directory(t);
  await publishCatalog(bundle.catalog, dir);
  assert.equal(await readFile(path.join(dir, 'schema/v0.2/agent.schema.json'), 'utf8'), stable()['agent.schema.json']);
});
