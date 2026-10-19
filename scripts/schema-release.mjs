import { execFileSync } from 'node:child_process'
import { isDeepStrictEqual } from 'node:util'
import { readFileSync, readdirSync, lstatSync, mkdirSync, writeFileSync, existsSync, mkdtempSync, rmSync } from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { fileURLToPath } from 'node:url'
import { readCatalog, checkCatalog, schemaInventory, checkSchemas, createBundle } from './schema-bundles.mjs'

const repository = 'agent-primitives/suite'
const catalogPath = 'docs/schema-catalog.json'
const empty = { version: 1, bundles: [], releases: {} }
const tagPattern = /^v0\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/
const shaPattern = /^[a-f0-9]{40}$/
const filenamePattern = /^[a-z][a-z0-9-]*\.schema\.json$/
const fail = message => { throw new Error(message) }

function options(args) {
  const result = {}
  const allowed = new Set(['repo', 'release', 'out', 'base', 'ref', 'catalog-ref', 'dir'])
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i].replace(/^--/, '')
    if (!args[i].startsWith('--') || !allowed.has(key) || !args[i + 1] || result[key]) fail('invalid or duplicate option')
    result[key] = args[i + 1]
  }
  return result
}

export function run(command, opt) {
  const root = path.resolve(opt.repo || '.')
  const git = (...args) => execFileSync('git', ['-C', root, ...args], { maxBuffer: 2 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] })
  const commit = ref => {
    const sha = git('rev-parse', '--verify', '--end-of-options', `${ref}^{commit}`).toString().trim()
    if (!shaPattern.test(sha)) fail('invalid source commit')
    return sha
  }
  const tagCommit = release => {
    if (!tagPattern.test(release)) fail('release must be an exact v0.N.P root tag')
    return commit(`refs/tags/${release}`)
  }
  const catalogAt = ref => {
    const sha = commit(ref)
    const present = git('ls-tree', '--name-only', sha, '--', catalogPath).toString().trim()
    return readCatalog(present ? JSON.parse(git('show', `${sha}:${catalogPath}`)) : empty)
  }
  const catalog = () => readCatalog(JSON.parse(readFileSync(path.join(root, catalogPath), 'utf8')))
  const schemasAt = ref => {
    const files = ref
      ? git('ls-tree', '-z', `${commit(ref)}:schema`).toString().split('\0').filter(Boolean).map(line => {
        const match = line.match(/^100644 blob [a-f0-9]{40}\t(.+)$/)
        if (!match) fail('schema entries must be ordinary non-executable files')
        return match[1]
      })
      : readdirSync(path.join(root, 'schema'))
    const schemas = {}
    for (const name of files.sort()) {
      if (!filenamePattern.test(name)) fail('unexpected schema filename')
      if (!ref && !lstatSync(path.join(root, 'schema', name)).isFile()) fail('schema entries must be regular files')
      const bytes = ref ? git('show', `${commit(ref)}:schema/${name}`) : readFileSync(path.join(root, 'schema', name))
      const text = bytes.toString('utf8')
      if (!Buffer.from(text).equals(bytes)) fail('schema is not valid UTF-8')
      schemas[name] = text
    }
    schemaInventory(schemas)
    return schemas
  }
  const verifySources = value => {
    for (const entry of value.bundles) {
      if (tagCommit(entry.release) !== entry.sourceCommit) fail(`catalog tag/source commit mismatch: ${entry.release}`)
      if (!isDeepStrictEqual(schemaInventory(schemasAt(entry.sourceCommit)), entry.schemas)) fail(`catalog inventory differs from tagged source: ${entry.release}`)
    }
    for (const [release, bundlePath] of Object.entries(value.releases)) {
      const entry = value.bundles.find(bundle => bundle.path === bundlePath)
      if (!isDeepStrictEqual(schemaInventory(schemasAt(tagCommit(release))), entry.schemas)) fail(`release mapping differs from tagged schema bytes: ${release}`)
    }
  }

  if (command === 'check') {
    const current = catalog()
    const trusted = opt['catalog-ref'] ? catalogAt(opt['catalog-ref']) : current
    verifySources(current)
    verifySources(trusted)
    if (opt.release) {
      if (!tagPattern.test(opt.release)) fail('release must be an exact v0.N.P root tag')
      checkSchemas(schemasAt(opt.ref || 'HEAD'), trusted, { release: opt.release })
    } else {
      let base = opt.base
      const event = process.env.SCHEMA_EVENT || ''
      if (event === 'push') {
        base = process.env.SCHEMA_BEFORE
        if (!shaPattern.test(base || '') || /^0+$/.test(base)) fail('push requires a nonzero before commit')
      } else if (event === 'pull_request') {
        commit('HEAD^2') // CI checks out the synthetic merge; first parent is the current base.
        base = commit('HEAD^1')
      } else {
        base ||= commit('HEAD^1')
      }
      const baseSha = commit(base)
      git('merge-base', '--is-ancestor', baseSha, 'HEAD')
      checkCatalog(current, catalogAt(baseSha))
      checkSchemas(schemasAt(), current)
      checkSchemas(schemasAt(), trusted)
    }
    console.log('Schema catalog, source and immutability checks passed')
    return
  }

  if (command === 'pack') {
    const sha = tagCommit(opt.release || '')
    const current = catalog()
    verifySources(current)
    const result = createBundle(opt.release, sha, schemasAt(sha), current)
    if (!opt.out) fail('pack requires --out')
    const out = path.resolve(opt.out)
    mkdirSync(out, { recursive: true })
    const asset = result.asset === null ? null : `schemas-${opt.release}.json`
    const outputs = {
      'catalog-candidate.json': Buffer.from(JSON.stringify(result.catalog, null, 2) + '\n'),
      'metadata.json': Buffer.from(JSON.stringify({ release: opt.release, sourceCommit: sha, asset }) + '\n')
    }
    if (asset) outputs[asset] = result.asset
    for (const [name, bytes] of Object.entries(outputs)) {
      const target = path.join(out, name)
      if (existsSync(target)) {
        if (!readFileSync(target).equals(bytes)) fail(`refusing to replace prepared output: ${name}`)
      } else writeFileSync(target, bytes, { flag: 'wx' })
    }
    console.log(JSON.stringify({ release: opt.release, sourceCommit: sha, asset, candidate: path.join(out, 'catalog-candidate.json') }))
    return
  }

  if (command === 'upload') {
    if (!opt.dir) fail('upload requires --dir')
    const dir = path.resolve(opt.dir)
    const meta = JSON.parse(readFileSync(path.join(dir, 'metadata.json'), 'utf8'))
    if (!tagPattern.test(meta.release || '') || !shaPattern.test(meta.sourceCommit || '')) fail('invalid prepared release metadata')
    if (meta.asset !== null && meta.asset !== `schemas-${meta.release}.json`) fail('invalid prepared asset filename')
    const trusted = catalog()
    verifySources(trusted)
    const recreated = createBundle(meta.release, meta.sourceCommit, schemasAt(meta.sourceCommit), trusted)
    const candidate = readCatalog(JSON.parse(readFileSync(path.join(dir, 'catalog-candidate.json'), 'utf8')))
    if (!isDeepStrictEqual(candidate, recreated.catalog)) fail('prepared catalog differs from tagged source and trusted catalog')
    if ((meta.asset === null) !== (recreated.asset === null)) fail('prepared metadata does not match stable patch reuse')
    if (meta.asset !== null && !recreated.asset.equals(readFileSync(path.join(dir, meta.asset)))) fail('prepared asset integrity mismatch')
    const gh = (...args) => execFileSync('gh', args, { maxBuffer: 2 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] })
    // Re-resolve annotated or lightweight tags remotely immediately before upload.
    let object = JSON.parse(gh('api', `repos/${repository}/git/ref/tags/${meta.release}`)).object
    for (let depth = 0; object?.type === 'tag' && depth < 4; depth++) {
      if (!shaPattern.test(object.sha || '')) fail('invalid remote tag object')
      object = JSON.parse(gh('api', `repos/${repository}/git/tags/${object.sha}`)).object
    }
    if (object?.type !== 'commit' || object.sha !== meta.sourceCommit) fail('remote tag changed since preparation')
    const release = JSON.parse(gh('api', `repos/${repository}/releases/tags/${meta.release}`))
    if (release.tag_name !== meta.release) fail('release/tag mismatch')
    if (meta.asset === null) { console.log('Patch reuses its existing minor asset; no upload'); return }
    const target = path.join(dir, meta.asset)
    const bytes = readFileSync(target)
    const existing = release.assets.find(asset => asset.name === meta.asset)
    if (existing) {
      const temp = mkdtempSync(path.join(os.tmpdir(), 'suite-existing-'))
      try {
        gh('release', 'download', meta.release, '--repo', repository, '--pattern', meta.asset, '--dir', temp)
        if (!readFileSync(path.join(temp, meta.asset)).equals(bytes)) fail('existing release asset differs; refusing replacement')
      } finally { rmSync(temp, { recursive: true, force: true }) }
      console.log('Identical asset already exists; left unchanged')
    } else {
      gh('release', 'upload', meta.release, target, '--repo', repository)
      console.log('Schema asset uploaded; review catalog-candidate.json in a separate PR')
    }
    return
  }
  fail('expected check, pack or upload')
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try { run(process.argv[2], options(process.argv.slice(3))) }
  catch (error) { console.error(`schema-release: ${error.message}`); process.exitCode = 1 }
}
