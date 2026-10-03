# Suitability assessment

Use this gate before generating a deployment package.

## Suitable

An existing ADK, CrewAI, or Claude Agent SDK agent is generally suitable when it can run headless behind a request/response interface with its dependencies, credentials, and data stores supplied through configuration.

A skill is generally suitable when its core behavior can be expressed as instructions plus bounded model calls, or when its scripts/services can be wrapped as explicit typed adapters. Typical examples include classification, extraction, summarization, drafting, data transformation, and read-only API lookup.

## Suitable with adaptations

Require an adaptation plan when the skill needs any of the following:

- Python, Node, or system packages not present in the baseline image
- source scripts that need typed wrappers, timeouts, or a restricted work directory
- MCP/app connectors that must become ordinary authenticated HTTP service adapters
- files or models that must be mounted, downloaded, or licensed separately
- asynchronous work, scheduling, persistence, retries, or approval workflows
- structured output that needs schema validation and repair
- data stores, vector stores, or session/memory backends that must be reached over the network or mounted
- an agent whose tools (shell, file writes, MCP servers) need tighter permissions, a dedicated workdir, or microVM isolation
- framework sessions or memory that are in-process today but must persist

State the adapter, dependency, credential, state, and behavior changes. Confirm changes that affect behavior, privacy, spending, or side effects.

## Not suitable without redesign

Stop when faithful behavior materially depends on:

- Codex/ChatGPT-only UI primitives, conversation state, browser tabs, desktop control, or a human operating an app during each run
- connectors or private services with no deployable API/authentication path
- data stores that cannot be reached from the chosen runtime, or that hold data the user cannot move or expose to it
- an agent that needs a human-in-the-loop prompt (interactive permission prompts, `input()`) on every run with no approval path
- arbitrary shell execution, unrestricted filesystem access, Docker socket access, or privilege escalation
- irreversible, financial, security-sensitive, or public actions with no deterministic controls and approval path
- host-specific data that cannot legally or technically be packaged or mounted
- unsupported architecture, GPU/runtime requirements, or interactive hardware with no selected deployment host
- missing or incompatible license/provenance for redistributed code, weights, fonts, or data
- a workflow whose essential quality depends on tools that the proposed runtime will not expose

Do not label a skill unsuitable merely because it requires ordinary engineering. Decline only when there is no faithful, safe package under the stated constraints.

## Required report

Return this short report before scaffolding:

```text
Classification: suitable | suitable with adaptations | not suitable
Core behavior preserved: ...
Source kind: skill | adk | crewai | claude-agent-sdk
Runtime dependencies: ...
Data stores and state: ...
External services and credentials (names only): ...
Side effects and approval needs: ...
License/provenance: ...
Required adaptations or blocker: ...
```

