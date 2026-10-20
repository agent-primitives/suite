# AgentSuite

Teams need to share an agent's instructions and tools without guessing which files and versions belong together.

> You hand a release-notes agent to another team whose tools support AgentSuite.
>
> Its instructions and tool definitions travel together, with fingerprints for referenced files.
>
> Their tooling checks the package before loading it into a runtime.

AgentSuite is a file format and Go library for tools that package or load agents.
It describes instructions, tool dependencies and relationships between agents.
It is not an agent runtime, image builder or registry client. Sharing a definition
does not guarantee the same behavior in every runtime.

**Status: draft specification and pre-1.0 library. Read the [compatibility policy](CONTRIBUTING.md#release-policy) before adopting it.**

## Try the validator

With Git and Go installed, check a bundled three-agent package:

```sh
git clone https://github.com/agent-primitives/suite.git
cd suite
GOWORK=off go test -count=1 -run '^TestCoordinatorWorkersFixtureIsConformant$' -v .
```

Expect **PASS**. This checks the [coordinator, writer and reviewer package](testdata/coordinator-workers/);
it does not run an agent, model or tool. It does not prove the agent is useful or
safe to execute. See the [Go requirements and library usage](docs/go.md) to
validate your own content.

## Go deeper

- [Go library](docs/go.md): validation, strict JSON decoding, content fingerprints and package scope.
- [Format specification](spec.md) and [JSON schemas](docs/schemas.md): the authoritative contract and its experimental parts.
- [Examples and conformance checks](docs/conformance.md): what validation establishes and what it does not.
- [Directory identity and migration](docs/directory-identity.md): how file metadata affects package identity.
- [Releases](docs/releases.md) and [contributing](CONTRIBUTING.md): compatibility, development checks and release policy.
- [Documentation site](https://suite.agent-primitives.dev/): tracks main and may include unreleased changes.

Licensed under the [MIT License](LICENSE). Copyright (c) Microsoft Corporation.
See [SECURITY.md](SECURITY.md) for private vulnerability reporting and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for the Microsoft community policy.
