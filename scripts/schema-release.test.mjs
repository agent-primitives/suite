import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { execFileSync, spawnSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, symlinkSync } from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const script = fileURLToPath(new URL('./schema-release.mjs', import.meta.url))
const empty = { version: 1, bundles: [], releases: {} }
function fixture(t, stable = false) {
  const root = mkdtempSync(path.join(os.tmpdir(), 'suite-release-'))
  t.after(() => rmSync(root, { recursive: true, force: true }))
  const git = (...args) => execFileSync('git', ['-C', root, ...args], { encoding: 'utf8' }).trim()
  git('init', '-q'); git('config', 'user.name', 'Schema fixture'); git('config', 'user.email', 'fixture@example.invalid')
  mkdirSync(path.join(root, 'schema')); mkdirSync(path.join(root, 'docs'))
  const schema = JSON.stringify({ $schema: 'https://json-schema.org/draft/2020-12/schema', $id: stable ? 'https://suite.agent-primitives.dev/schema/v0.5/suite.schema.json' : 'https://kaimahi.dev/schemas/agentsuite/v1/suite.schema.json', type: 'object' }) + '\n'
  writeFileSync(path.join(root, 'schema/suite.schema.json'), schema)
  writeFileSync(path.join(root, 'docs/schema-catalog.json'), JSON.stringify(empty))
  git('add', '.'); git('commit', '-qm', 'fixture'); git('tag', stable ? 'v0.5.0' : 'v0.4.0')
  const run = (...args) => spawnSync(process.execPath, [script, ...args, '--repo', root], { encoding: 'utf8', env: { ...process.env, GITHUB_EVENT_NAME: '', SCHEMA_EVENT: '' } })
  return { root, git, run, schema, out: path.join(root, 'output') }
}

test('pack reads exact tagged bytes, not changed working files, and emits a catalog candidate', t => {
  const f = fixture(t)
  writeFileSync(path.join(f.root, 'schema/suite.schema.json'), '{}')
  const result = f.run('pack', '--release', 'v0.4.0', '--out', f.out)
  assert.equal(result.status, 0, result.stderr)
  const bundle = JSON.parse(readFileSync(path.join(f.out, 'schemas-v0.4.0.json')))
  assert.equal(bundle.schemas['suite.schema.json'], f.schema)
  assert.equal(bundle.sourceCommit, f.git('rev-parse', 'v0.4.0^{commit}'))
  const candidate = JSON.parse(readFileSync(path.join(f.out, 'catalog-candidate.json')))
  assert.equal(candidate.releases['v0.4.0'], 'archive/v0.4.0')
})

test('experimental flow is refused as a patch addition and retained in a new minor asset', t => {
  const f = fixture(t, true)
  assert.equal(f.run('pack', '--release', 'v0.5.0', '--out', f.out).status, 0)
  writeFileSync(path.join(f.root, 'docs/schema-catalog.json'), readFileSync(path.join(f.out, 'catalog-candidate.json')))
  const name = 'kmx-flow-v1alpha1.schema.json'
  const text = minor => JSON.stringify({ $id: `https://suite.agent-primitives.dev/schema/v0.${minor}/${name}`, type: 'object', properties: { schemaVersion: { const: 'kmx.flow/v1alpha1' } } }) + '\n'
  writeFileSync(path.join(f.root, 'schema', name), text(5))
  f.git('add', '.'); f.git('commit', '-qm', 'new experimental schema'); f.git('tag', 'v0.5.1')
  assert.notEqual(f.run('pack', '--release', 'v0.5.1', '--out', path.join(f.root, 'patch')).status, 0)
  // Synthetic test tags only: no product release number is selected here.
  writeFileSync(path.join(f.root, 'schema/suite.schema.json'), f.schema.replace('/v0.5/', '/v0.9/'))
  writeFileSync(path.join(f.root, 'schema', name), text(9))
  f.git('add', '.'); f.git('commit', '-qm', 'new minor inventory'); f.git('tag', 'v0.9.0')
  const out = path.join(f.root, 'minor')
  const packed = f.run('pack', '--release', 'v0.9.0', '--out', out)
  assert.equal(packed.status, 0, packed.stderr)
  const asset = JSON.parse(readFileSync(path.join(out, 'schemas-v0.9.0.json')))
  assert.equal(asset.schemas[name], text(9))
  assert.equal(asset.schemas['suite.schema.json'], f.schema.replace('/v0.5/', '/v0.9/'))
})

test('pack refuses executable link entries and malformed release inputs', t => {
  const f = fixture(t)
  symlinkSync('../docs/schema-catalog.json', path.join(f.root, 'schema/link.schema.json'))
  f.git('add', '.'); f.git('commit', '-qm', 'link'); f.git('tag', 'v0.4.1')
  assert.notEqual(f.run('pack', '--release', 'v0.4.1', '--out', f.out).status, 0)
  assert.notEqual(f.run('pack', '--release', 'v0.4.0;touch sentinel', '--out', f.out).status, 0)
  assert.throws(() => readFileSync(path.join(f.root, 'sentinel')), /ENOENT/)
})

test('guard allows first catalog introduction but refuses deletion of a tracked catalog', t => {
  const f = fixture(t)
  f.git('rm', 'docs/schema-catalog.json'); f.git('commit', '-qm', 'before catalog')
  const before = f.git('rev-parse', 'HEAD')
  mkdirSync(path.join(f.root, 'docs'), { recursive: true })
  writeFileSync(path.join(f.root, 'docs/schema-catalog.json'), JSON.stringify(empty))
  assert.equal(f.run('check', '--base', before).status, 0)
  f.git('add', 'docs/schema-catalog.json'); f.git('commit', '-qm', 'catalog')
  const introduced = f.git('rev-parse', 'HEAD')
  rmSync(path.join(f.root, 'docs/schema-catalog.json'))
  const missing = f.run('check', '--base', introduced)
  assert.notEqual(missing.status, 0)
  assert.match(missing.stderr, /schema-catalog\.json/)
})

test('guard refuses missing/nonancestor push baselines rather than falling back', t => {
  const f = fixture(t)
  const command = before => spawnSync(process.execPath, [script, 'check', '--repo', f.root], { encoding: 'utf8', env: { ...process.env, SCHEMA_EVENT: 'push', SCHEMA_BEFORE: before } })
  assert.notEqual(command('0'.repeat(40)).status, 0)
  assert.notEqual(command('f'.repeat(40)).status, 0)
  const branch = f.git('branch', '--show-current')
  f.git('checkout', '-q', '--orphan', 'unrelated'); f.git('commit', '-qm', 'other root')
  const unrelated = f.git('rev-parse', 'HEAD')
  f.git('checkout', '-q', branch)
  assert.notEqual(command(unrelated).status, 0)
})

test('stable patch pre-tag check fails closed without a catalogued minor', t => {
  const f = fixture(t, true)
  const result = f.run('check', '--release', 'v0.5.1', '--ref', f.git('rev-parse', 'HEAD'))
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /minor|catalog/i)
})

test('catalog guard verifies entries against their tagged source, not self-attested metadata', t => {
  const f = fixture(t)
  assert.equal(f.run('pack', '--release', 'v0.4.0', '--out', f.out).status, 0)
  const catalog = JSON.parse(readFileSync(path.join(f.out, 'catalog-candidate.json')))
  catalog.bundles[0].sourceCommit = 'a'.repeat(40)
  writeFileSync(path.join(f.root, 'docs/schema-catalog.json'), JSON.stringify(catalog))
  assert.notEqual(f.run('check', '--base', f.git('rev-parse', 'HEAD')).status, 0)
})

test('stable patch pack reuses the catalogued minor and never emits a patch asset', t => {
  const f = fixture(t, true)
  assert.equal(f.run('pack', '--release', 'v0.5.0', '--out', f.out).status, 0)
  writeFileSync(path.join(f.root, 'docs/schema-catalog.json'), readFileSync(path.join(f.out, 'catalog-candidate.json')))
  f.git('add', 'docs/schema-catalog.json'); f.git('commit', '-qm', 'catalog'); f.git('tag', 'v0.5.1')
  const patchOut = path.join(f.root, 'patch')
  const result = f.run('pack', '--release', 'v0.5.1', '--out', patchOut)
  assert.equal(result.status, 0, result.stderr)
  assert.equal(JSON.parse(readFileSync(path.join(patchOut, 'metadata.json'))).asset, null)
  assert.equal(JSON.parse(readFileSync(path.join(patchOut, 'catalog-candidate.json'))).releases['v0.5.1'], 'v0.5')
  assert.throws(() => readFileSync(path.join(patchOut, 'schemas-v0.5.1.json')), /ENOENT/)
})

test('PR guard compares with the synthetic merge first parent, not an older empty catalog', t => {
  const f = fixture(t)
  assert.equal(f.run('pack', '--release', 'v0.4.0', '--out', f.out).status, 0)
  writeFileSync(path.join(f.root, 'docs/schema-catalog.json'), readFileSync(path.join(f.out, 'catalog-candidate.json')))
  f.git('add', 'docs/schema-catalog.json'); f.git('commit', '-qm', 'published catalog')
  const baseBranch = f.git('branch', '--show-current')
  f.git('checkout', '-qb', 'remove-history')
  writeFileSync(path.join(f.root, 'docs/schema-catalog.json'), JSON.stringify(empty))
  f.git('add', 'docs/schema-catalog.json'); f.git('commit', '-qm', 'drop history')
  f.git('checkout', '-q', baseBranch); f.git('merge', '--no-ff', '-qm', 'synthetic merge', 'remove-history')
  const result = spawnSync(process.execPath, [script, 'check', '--repo', f.root], { encoding: 'utf8', env: { ...process.env, SCHEMA_EVENT: 'pull_request' } })
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /deleted|mutated/)
})

test('release-line checks use the trusted main catalog before tagging a patch', t => {
  const f = fixture(t, true)
  assert.equal(f.run('pack', '--release', 'v0.5.0', '--out', f.out).status, 0)
  writeFileSync(path.join(f.root, 'docs/schema-catalog.json'), readFileSync(path.join(f.out, 'catalog-candidate.json')))
  f.git('add', 'docs/schema-catalog.json'); f.git('commit', '-qm', 'main catalog')
  f.git('update-ref', 'refs/remotes/origin/main', f.git('rev-parse', 'HEAD'))
  f.git('checkout', '-q', '--detach', 'v0.5.0')
  const args = ['check', '--release', 'v0.5.1', '--ref', 'HEAD', '--catalog-ref', 'refs/remotes/origin/main']
  assert.equal(f.run(...args).status, 0)
  writeFileSync(path.join(f.root, 'schema/suite.schema.json'), f.schema + ' ')
  f.git('add', 'schema/suite.schema.json'); f.git('commit', '-qm', 'patch byte drift')
  const result = f.run(...args)
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /changed|minor/)
})

function publisher(t, patch = false) {
  const f = fixture(t, patch)
  assert.equal(f.run('pack', '--release', patch ? 'v0.5.0' : 'v0.4.0', '--out', f.out).status, 0)
  if (patch) {
    writeFileSync(path.join(f.root, 'docs/schema-catalog.json'), readFileSync(path.join(f.out, 'catalog-candidate.json')))
    f.git('add', 'docs/schema-catalog.json'); f.git('commit', '-qm', 'catalog'); f.git('tag', 'v0.5.1')
    f.out = path.join(f.root, 'patch-output')
    assert.equal(f.run('pack', '--release', 'v0.5.1', '--out', f.out).status, 0)
  }
  const release = patch ? 'v0.5.1' : 'v0.4.0'
  const bin = path.join(f.root, 'bin')
  mkdirSync(bin)
  const statePath = path.join(f.root, 'remote-state.json')
  const remote = path.join(f.root, 'remote-asset.json')
  const state = { sourceCommit: f.git('rev-parse', `${release}^{commit}`), tag_name: release, assets: [] }
  const save = () => writeFileSync(statePath, JSON.stringify(state))
  save()
  writeFileSync(path.join(bin, 'gh'), `#!/usr/bin/env node
const fs = require('node:fs'), path = require('node:path');
const statePath = process.env.FAKE_STATE, remote = process.env.FAKE_ASSET;
const state = JSON.parse(fs.readFileSync(statePath)), args = process.argv.slice(2);
if (args[0] === 'api' && args[1].includes('/git/ref/tags/')) console.log(JSON.stringify({object:{type:'commit',sha:state.sourceCommit}}));
else if (args[0] === 'api' && args[1].includes('/releases/tags/')) { if(state.missing)process.exit(1); console.log(JSON.stringify(state)); }
else if (args[0] === 'release' && args[1] === 'upload') { fs.copyFileSync(args[3],remote); state.assets=[{name:path.basename(args[3])}]; fs.writeFileSync(statePath,JSON.stringify(state)); }
else if (args[0] === 'release' && args[1] === 'download') fs.copyFileSync(remote,path.join(args[args.indexOf('--dir')+1],'schemas-v0.4.0.json'));
else process.exit(2);
`, { mode: 0o755 })
  const upload = () => spawnSync(process.execPath, [script, 'upload', '--dir', f.out, '--repo', f.root], { encoding: 'utf8', env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, FAKE_STATE: statePath, FAKE_ASSET: remote } })
  return { ...f, state, save, remote, upload }
}

test('publisher uploads absent assets, accepts identical retries, and refuses replacement or moved tags', t => {
  const f = publisher(t)
  let result = f.upload()
  assert.equal(result.status, 0, result.stderr)
  const original = readFileSync(path.join(f.out, 'schemas-v0.4.0.json'))
  assert.deepEqual(readFileSync(f.remote), original)
  result = f.upload()
  assert.equal(result.status, 0, result.stderr)
  writeFileSync(f.remote, 'changed remote bytes')
  result = f.upload()
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /existing release asset differs/)
  assert.equal(readFileSync(f.remote, 'utf8'), 'changed remote bytes')
  f.state.sourceCommit = 'a'.repeat(40); f.save()
  result = f.upload()
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /remote tag changed/)
})

test('publisher refuses fake patch reuse for a non-patch release', t => {
  const f = publisher(t)
  const metadataPath = path.join(f.out, 'metadata.json')
  const metadata = JSON.parse(readFileSync(metadataPath))
  metadata.asset = null
  writeFileSync(metadataPath, JSON.stringify(metadata))
  const result = f.upload()
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /stable.patch|reuse/)
  assert.throws(() => readFileSync(f.remote), /ENOENT/)
})

test('genuine patch reuse verifies its prepared candidate and tagged source without uploading', t => {
  const f = publisher(t, true)
  let result = f.upload()
  assert.equal(result.status, 0, result.stderr)
  assert.throws(() => readFileSync(f.remote), /ENOENT/)
  const candidatePath = path.join(f.out, 'catalog-candidate.json')
  const candidate = JSON.parse(readFileSync(candidatePath))
  delete candidate.releases['v0.5.1']
  writeFileSync(candidatePath, JSON.stringify(candidate))
  result = f.upload()
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /catalog.*tagged source|candidate/)
  rmSync(candidatePath)
  result = f.upload()
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /catalog-candidate/)
})

test('publisher rejects self-consistent prepared bytes that differ from the tagged source', t => {
  const f = publisher(t)
  const assetPath = path.join(f.out, 'schemas-v0.4.0.json')
  const asset = JSON.parse(readFileSync(assetPath))
  asset.schemas['suite.schema.json'] = asset.schemas['suite.schema.json'].replace('"object"', '"array"')
  const bytes = Buffer.from(JSON.stringify(asset) + '\n')
  writeFileSync(assetPath, bytes)
  const candidatePath = path.join(f.out, 'catalog-candidate.json')
  const candidate = JSON.parse(readFileSync(candidatePath))
  candidate.bundles[0].sha256 = createHash('sha256').update(bytes).digest('hex')
  candidate.bundles[0].schemas['suite.schema.json'].sha256 = createHash('sha256').update(asset.schemas['suite.schema.json']).digest('hex')
  writeFileSync(candidatePath, JSON.stringify(candidate))
  const result = f.upload()
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /tagged source/)
  assert.throws(() => readFileSync(f.remote), /ENOENT/)
})
