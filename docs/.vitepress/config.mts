import { cp } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { slug } from 'github-slugger'
import { defineConfig } from 'vitepress'

const root = fileURLToPath(new URL('../..', import.meta.url))
const repository = 'https://github.com/agent-primitives/suite'
const sourceRef = process.env.GITHUB_SHA || 'main'
const pages = ['index', 'schemas', 'conformance', 'go', 'releases', 'hosting']

export default defineConfig({
  title: 'AgentSuite',
  description: 'Portable, content-addressed agent definitions and conformance.',
  lang: 'en-US',
  srcDir: '..',
  base: '/',
  cleanUrls: true,
  useWebFonts: false,
  rewrites: Object.fromEntries(pages.map(page => [`docs/${page}.md`, `${page}.md`])),
  srcExclude: ['README.md', 'CONTRIBUTING.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', '.github/**', 'testdata/**', 'node_modules/**'],
  markdown: {
    anchor: { slugify: slug },
    config(md) {
      // Preserve checkout-relative Markdown while publishing raw schemas and source fixtures.
      const render = md.renderer.rules.link_open || ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))
      md.renderer.rules.link_open = (tokens, index, options, env, self) => {
        const token = tokens[index]
        const href = token.attrGet('href') || ''
        const relative = href.replace(/^\.\.\//, '')
        if (/^spec\.md(?:#|$)/.test(relative)) {
          token.attrSet('href', `/${relative}`)
        } else if (relative.startsWith('schema/')) {
          token.attrSet('href', relative === 'schema/' ? '/schemas' : `/${relative}`)
        } else if (relative.startsWith('testdata/')) {
          token.attrSet('href', `${repository}/tree/${sourceRef}/${relative}`)
        } else if (relative.startsWith('CONTRIBUTING.md')) {
          token.attrSet('href', `${repository}/blob/${sourceRef}/${relative}`)
        }
        return render(tokens, index, options, env, self)
      }
    }
  },
  vite: {
    publicDir: 'docs/public',
    resolve: {
      alias: {
        'vue/server-renderer': path.join(root, 'docs/node_modules/vue/server-renderer/index.mjs'),
        vue: path.join(root, 'docs/node_modules/vue/dist/vue.runtime.esm-bundler.js')
      }
    }
  },
  async buildEnd(config) {
    // Copy bytes, not parsed JSON: schema IDs and release provenance are immutable.
    await cp(path.join(root, 'schema'), path.join(config.outDir, 'schema'), { recursive: true })
  },
  themeConfig: {
    nav: [
      { text: 'Specification', link: '/spec' },
      { text: 'Schemas', link: '/schemas' },
      { text: 'Go usage', link: '/go' },
      { text: 'main · development', link: '/releases' }
    ],
    sidebar: [
      { text: 'Overview', link: '/' },
      { text: 'Specification', link: '/spec' },
      { text: 'Schemas', link: '/schemas' },
      { text: 'Conformance fixtures', link: '/conformance' },
      { text: 'Go usage', link: '/go' },
      { text: 'Versions and releases', link: '/releases' },
      { text: 'Site hosting', link: '/hosting' }
    ],
    search: { provider: 'local' },
    outline: [2, 3],
    socialLinks: [{ icon: 'github', link: repository }],
    editLink: { pattern: `${repository}/edit/main/:path` },
    footer: { message: 'Development documentation from the repository Markdown.' }
  }
})
