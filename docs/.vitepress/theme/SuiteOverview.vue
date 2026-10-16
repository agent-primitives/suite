<script setup>
import { latestRelease } from '../release.mjs'

const releaseUrl = `https://github.com/agent-primitives/suite/tree/${latestRelease}`
</script>

<template>
  <main class="suite-home" aria-labelledby="suite-title">
    <header class="suite-intro">
      <div class="suite-intro-copy">
        <p class="suite-family">agent-primitives / suite</p>
        <h1 id="suite-title">AgentSuite</h1>
        <p class="suite-lead">A content-addressed format for agent definitions.</p>
        <p class="suite-summary">Package agents, their instructions and exact tool dependencies as an open OCI artifact. One format for the definition, independent of the runtime.</p>
        <a class="suite-primary" href="/spec">Read the specification <span aria-hidden="true">→</span></a>
        <p class="suite-status"><a :href="releaseUrl">{{ latestRelease }}</a><span aria-hidden="true">·</span><a href="/releases">docs track main</a></p>
      </div>

      <figure class="suite-specimen" aria-labelledby="suite-contents-caption">
        <figcaption id="suite-contents-caption">Inside a suite <span>Content graph</span></figcaption>
        <div class="suite-root"><code>agentsuite.json</code><span>Suite manifest</span></div>
        <ul class="suite-tree">
          <li><span class="suite-tree-name">Agents</span><span>Instructions &amp; tool requirements</span></li>
          <li><span class="suite-tree-name">ToolProviders</span><span>Tool contracts &amp; exact variants</span></li>
          <li><span class="suite-tree-name">Compositions</span><span>Agent &amp; provider selections</span></li>
          <li><span class="suite-tree-name">Build profiles</span><span>Sandbox build inputs</span></li>
          <li><span class="suite-tree-name">Evaluations <small>optional</small></span><span>Cases &amp; authored assertions</span></li>
        </ul>
        <p class="suite-specimen-note">A closed graph of referenced content, distributed as an OCI artifact.</p>
      </figure>
    </header>

    <nav class="suite-resources" aria-label="Format resources">
      <a href="/spec"><span class="suite-resource-index" aria-hidden="true">01</span><span><strong>Specification</strong><span>The format &amp; its requirements</span></span><span aria-hidden="true">→</span></a>
      <a href="/schemas"><span class="suite-resource-index" aria-hidden="true">02</span><span><strong>JSON schemas</strong><span>Document shapes &amp; raw downloads</span></span><span aria-hidden="true">→</span></a>
      <a href="/go"><span class="suite-resource-index" aria-hidden="true">03</span><span><strong>Go package</strong><span>Decode, identify &amp; validate offline</span></span><span aria-hidden="true">→</span></a>
      <a href="/conformance"><span class="suite-resource-index" aria-hidden="true">04</span><span><strong>Conformance</strong><span>Fixtures that exercise the contract</span></span><span aria-hidden="true">→</span></a>
    </nav>

    <section class="suite-identity" aria-labelledby="identity-title">
      <div>
        <h2 id="identity-title">Identity follows the content.</h2>
        <p>Manifest identities use SHA-256 over RFC 8785 canonical JSON. Regular files are identified by their exact bytes. References bind the graph together with digests and sizes.</p>
        <a class="suite-text-link" href="/spec#6-identity">Read the identity rules <span aria-hidden="true">→</span></a>
      </div>
      <div class="suite-identity-flow" role="img" aria-label="Manifest identity: canonical JSON, then SHA-256, then content digest">
        <span>Manifest</span><span aria-hidden="true">↓</span><code>RFC 8785 · canonical JSON</code><span aria-hidden="true">↓</span><code>SHA-256 → content digest</code>
      </div>
    </section>

    <section class="suite-validation" aria-labelledby="validation-title">
      <h2 id="validation-title">Validate the format.<br /> Keep runtime claims separate.</h2>
      <div>
        <p>JSON schemas check document shapes. The Go validator also checks canonical content, descriptors, references and the closed graph, from an extracted directory or OCI image layout.</p>
        <p class="suite-boundary">Validation does not execute agents, tools or evaluations. Packaged evaluation cases are requirements, not evidence of a passing run.</p>
        <p>v0.2.0 adds portable evaluation evidence with an offline verifier, <a class="suite-evidence-link" href="/spec#824-portable-evaluation-evidence"><code>VerifyEvaluation</code></a>.</p>
        <a class="suite-text-link" href="/conformance">See what conformance means <span aria-hidden="true">→</span></a>
      </div>
    </section>

    <footer class="suite-context">
      <div>
        <h2>Part of agent-primitives</h2>
        <p><a href="https://kaimahi.dev/">kmx</a> uses AgentSuite for packaging and validation. <a href="https://github.com/agent-primitives/sessions">agentsessions</a> is a consumer in the runtime ecosystem. An <a href="https://github.com/orka-agents/orka">Orka</a> dashboard integration is <strong>planned</strong>, not provided by this library.</p>
      </div>
      <div class="suite-source">
        <a href="https://github.com/agent-primitives/suite">Source on GitHub <span aria-hidden="true">↗</span></a>
        <p>These pages track main and may include unreleased changes. Use the <a :href="releaseUrl">{{ latestRelease }} tag</a> for a fixed contract.</p>
      </div>
    </footer>
  </main>
</template>
