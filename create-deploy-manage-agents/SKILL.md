---
name: create-deploy-manage-agents
description: Package a skill (SKILL.md, local or GitHub) or an existing agent built with Google ADK, CrewAI, or the Anthropic Claude Agent SDK into a runnable, Dockerized agent service, run either as a plain Docker container or inside a Docker Sandboxes microVM. Use when a user asks to containerize, serve, deploy, expose through HTTP or CLI, or turn a skill or agent project into a deployable agent using Gemini, Ollama, OpenAI, or Anthropic Claude. Gather the source, runtime, model provider, input/output contract, data stores, and required API keys; assess portability and safety before generating code; decline or explain remediation when the source cannot be safely or faithfully deployed this way.
---

# Create, deploy, and manage agents

Produce a complete deployment package, not only a Dockerfile or architecture description. Keep secrets out of source, images, logs, and committed environment files.

## 1. Gather the core contract

Before inspecting or generating code, ask for all missing items in one concise message:

1. **Source:** local path/name or GitHub repository URL plus optional ref and subdirectory, and what it is: a **skill** (`SKILL.md`), a **Google ADK** agent, a **CrewAI** crew, or a **Claude Agent SDK** agent ("Anthropic harness"). If the user is unsure, say you will detect it.
2. **LLM provider and model:** for a skill, Gemini, Ollama, OpenAI, or Anthropic Claude plus the exact model name. For an existing agent, default to the provider and model it is already configured with and ask only whether to keep them. For Ollama, ask whether it runs on the Docker host or in a separate service.
3. **Input:** transport (`HTTP`, `CLI`, or both), payload shape, required fields, attachments, size limits, and one representative example.
4. **Output:** response shape or MIME type, required fields, error behavior, destination, and one representative example.
5. **Installation runtime:** plain **Docker** (container on the host Docker engine) or **Docker microVM** (Docker Sandboxes via `sbx`, each agent isolated in its own microVM). Briefly state the trade-off: Docker is simplest and most portable; microVM adds a VM isolation boundary and egress policy, but needs `sbx`, a Docker login, and supported host virtualization.

Always ask the runtime question explicitly, even when the user only said "Docker". Do not default it. Record the answer and follow the matching path in every later step.

Ask whether the user wants package artifacts only or an actual deployment if deployment is mentioned. Do not deploy or publish without separate explicit approval.

If the source or I/O contract is still ambiguous, pause generation and resolve it. Do not infer a materially different interface.

If the user chose **Docker microVM**, check the prerequisites in [references/docker-sandboxes.md](references/docker-sandboxes.md) now (`sbx version`, login state, `sbx diagnose`). If they fail and cannot be fixed, tell the user and offer the plain Docker runtime instead of silently switching.

## 2. Resolve and inspect the source

For a local skill name, search the configured skill roots, project `.agents/skills` and `.codex/skills`, and explicit user paths. Require exactly one match. For an agent project, use the path the user gave.

For GitHub:

- Resolve the exact repository, ref, and subdirectory.
- Use existing authenticated access for private repositories; never request a token in chat or put one in a URL.
- Clone or download into a temporary directory and pin the resolved commit in the generated package metadata.
- Review files before executing any source script.

For a skill, read the complete `SKILL.md` and follow its direct links to required references, scripts, and assets. For an agent, find its entrypoint (`root_agent`, the `@CrewBase` class, or the `ClaudeAgentOptions`/`query` call), its config files, tools, and dependency manifest. In both cases inventory runtimes, dependencies, external tools, connectors, MCP servers, network services, data stores, credentials, side effects, licenses, and host assumptions.

Run `scripts/assess_skill.py <source-directory>` for a repeatable inventory. It reports `detected_kinds`, the environment variable names the code reads (never values), and data-store references. Then apply [references/suitability.md](references/suitability.md), and for an agent also [references/agent-frameworks.md](references/agent-frameworks.md). The scan is evidence, not an automatic approval. If the detected kind differs from what the user said, or several frameworks are detected, confirm the entrypoint with the user.

## 3. Confirm data stores, credentials, and external services

Using the inventory, ask the remaining questions in one message. List what you found so the user confirms or corrects it instead of starting from scratch, and skip anything that does not apply:

1. **Data stores:** for each database, vector store, cache, object storage bucket, or file path the source uses: where it lives (managed service, host, another container, or not needed), how the container reaches it, read-only or read-write, and whether it holds personal, regulated, or production data. Ask whether verification should use a test or dev instance.
2. **State and memory:** must sessions, conversation history, agent memory, or job results survive a restart? If yes, where (database, volume, managed service)?
3. **API keys and credentials:** each key or credential the agent needs, covering the model provider, tool APIs (search, scraping, SaaS), data stores, and MCP servers. Ask how each reaches the container at runtime: environment variable, secret manager, mounted cloud credentials, or `sbx secret` for microVM. Ask only for variable names and delivery method, never the secret values.
4. **External services and tools:** APIs, MCP servers, webhooks, or downstream systems the agent calls, which of them cause side effects (send, write, pay, publish), and which hosts egress must allow.
5. **Operational limits:** expected run time per request, concurrency, and cost or token ceilings if the user has them.

Never accept a secret pasted in chat. If one is pasted, do not repeat or store it; tell the user to rotate it and supply it through the environment.

Every answer flows into the package: `.env.example` (names only), config validation, `/readyz` checks, volumes, egress rules, and the hand-off.

## 4. Make a suitability decision

Classify the source before scaffolding:

- **Suitable:** an instruction/reference skill can run through an LLM with the requested interface, or an agent can run as written behind the requested interface.
- **Suitable with adaptations:** scripts, remote tools, data stores, or framework services can be exposed or connected through bounded, typed adapters and configuration without changing the promised behavior.
- **Not suitable:** faithful operation depends on unavailable Codex UI/tooling, interactive desktop control, undeployable local state, unreachable data stores, unsupported runtimes, unclear rights, or unsafe side effects without an approval/control plane.

Tell the user the classification and its concrete reasons. For adaptations, state what will change and obtain confirmation when it changes behavior, cost, privacy, or external side effects. For an unsuitable source, stop and offer specific remediation; do not emit a misleading prompt-only wrapper.

## 5. Design the smallest faithful agent

Read [references/package-contract.md](references/package-contract.md) before implementation, [references/providers.md](references/providers.md) for the selected provider of a skill, and [references/agent-frameworks.md](references/agent-frameworks.md) for an existing agent.

Use a synchronous request service for short work. Add a queue and durable job store only when the contract includes long-running, retryable, scheduled, or restart-safe work.

Keep these boundaries even in a small package:

- transport and input validation
- agent/application service
- model gateway (skills) or framework runner (existing agents)
- typed tool adapters and data-store clients
- configuration and secret loading
- structured telemetry
- output validation

Do not let the model execute arbitrary shell commands or choose arbitrary file paths. Wrap required source scripts as explicit allowlisted functions with validated arguments, fixed working directories, timeouts, output limits, and least privilege. Do not widen an existing agent's tool permissions. Put destructive, financial, security-sensitive, or public actions behind deterministic policy checks and explicit approval.

## 6. Scaffold and adapt the package

Start from the bundled template:

```bash
python scripts/scaffold_agent.py \
  --name <agent-name> \
  --source-dir <resolved-skill-or-agent-directory> \
  --source-kind <skill|adk|crewai|claude-agent-sdk> \
  --output-dir <new-empty-directory> \
  --provider <gemini|ollama|openai|anthropic> \
  --model <exact-model-name> \
  --transport <http|cli|both> \
  --runtime <docker|microvm> \
  --input-description '<concise contract>' \
  --output-description '<concise contract>'
```

The script refuses to overwrite a non-empty directory. It copies the source (to `skill_source/` for a skill, `agent_source/` for an agent), records provenance including the source kind and runtime, substitutes package settings, and creates a Python/Docker baseline. For an agent kind it also writes `src/skill_agent/runner.py`, a framework runner to wire in as described in [references/agent-frameworks.md](references/agent-frameworks.md). With `--runtime microvm` it emits `deploy/microvm.sh`; with `--runtime docker` that file is omitted. For an existing agent, pass its current provider and model.

Then adapt the generated package:

1. Replace the generic request and response models with explicit Pydantic types matching the agreed examples.
2. Include only source files needed at runtime; exclude unrelated, secret, cached, generated, or licensed-prohibited files.
3. For an agent, wire in the framework runner, remove the unused prompt/gateway modules, and install the agent's pinned dependencies.
4. Add typed adapters for every required source script or external service, and configure every confirmed data store from environment variables. Never rely on an instruction that names a tool the runtime does not actually provide.
5. Parse and validate structured model output before returning or taking action. Retry malformed output at most once with a corrective prompt.
6. Add durable state, volumes, idempotency, bounded retries, and a queue only when the confirmed state and run-time answers require them.
7. Update generated tests to cover the real input/output schema, adapters, and the runner, using fakes with no network calls.
8. List every confirmed credential and data-store variable in `.env.example` with safe placeholders only. Make `/readyz` and config validation fail clearly when a required one is missing. Inject real values only at runtime.

Adapt the run instructions to the chosen runtime:

- **Docker:** document `docker build` and `docker run` as in the template README, including required `-e` variables and any volumes or networks for data stores.
- **Docker microVM:** read [references/docker-sandboxes.md](references/docker-sandboxes.md), adapt `deploy/microvm.sh` (env vars, port, egress for model APIs, tool APIs, and data stores), and replace the README run section with the microVM workflow. Keep one Dockerfile for both runtimes.

For Ollama on the host, use `host.docker.internal` on Docker Desktop and document the Linux host-gateway alternative; under the microVM runtime, verify reachability as described in the sandboxes reference. The same applies to data stores on the host. Add an Ollama or database Compose service only when the user explicitly wants it managed with the package; model downloads are operational steps and may be large.

## 7. Verify before handoff

Run every applicable check in [references/verification.md](references/verification.md). At minimum:

1. Validate the source copy and generated provenance.
2. Run formatting/static checks and unit tests with a fake model gateway or fake framework runner.
3. Build the Docker image.
4. Run the container without real credentials on its deterministic health path.
5. If credentials are available through the environment and the user authorizes usage, run one minimal live request against test data stores where they exist; never print a key.
6. Stop the container gracefully and inspect the final diff.

For the **Docker microVM** runtime, perform steps 3–6 through `deploy/microvm.sh` and `sbx` (build inside the sandbox, check `/healthz` on the published loopback port, then `sbx stop`). Creating a local sandbox is a local run; `sbx rm` and any `sbx --cloud` command need explicit approval.

Never write to a production data store during verification without explicit approval. If Docker, `sbx`, provider access, a data store, or another prerequisite is unavailable, finish safe source work and state exactly which verification remains. Never claim the source was faithfully converted if required tools or behaviors were omitted.

## 8. Hand off

Lead with what works and include:

- package location, source kind, and source commit/path
- chosen runtime (Docker or Docker microVM) and its prerequisites
- suitability result and adaptations made
- exact test and container results
- required environment variable names, grouped by model provider, tools, and data stores
- data stores and state: where each is expected to live, volumes, and persistence
- exact build and run commands for the chosen runtime (including stop/remove for microVM)
- request/response example using the agreed contract
- deliberate limitations and any unverified live-provider or data-store step
