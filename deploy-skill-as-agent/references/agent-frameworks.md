# Packaging an existing agent (ADK, CrewAI, Claude Agent SDK)

Use this reference when the source is an agent project rather than a `SKILL.md` skill. The goal is to containerize the agent as written. Do not rewrite it into the template's prompt + model gateway, and do not change its framework, model, or provider unless the user asks.

## What is kept and what is replaced

From the template, keep: the non-root Dockerfile shape, FastAPI transport (`/healthz`, `/readyz`, `/v1/invoke`), CLI, Pydantic schemas, JSON logging, `.dockerignore`, and `deploy/microvm.sh` when chosen.

Replace: `prompt.py`, `providers.py`, and the model call in `service.py`. The scaffold writes `src/skill_agent/runner.py` with a `FrameworkRunner` starting point. Wire it in:

1. `AgentService.__init__` takes a runner instead of a `ModelGateway`; `invoke` calls `await runner.run(request.input)` and keeps the size check, job ID, and timing.
2. `api.py` and `cli.py` build `FrameworkRunner()` instead of `HttpModelGateway`. `create_app` accepts a runner so tests can inject a fake.
3. `config.py`: drop `LLM_PROVIDER`/`LLM_MODEL` validation that the framework does not use, and validate the variables this agent actually requires (from the scan and the user's answers). `/readyz` must not make a billable call.
4. Delete `prompt.py`, `providers.py`, and `tests/test_providers.py`; update the remaining tests to use a fake runner.
5. Add the agent's own dependencies. Prefer its lockfile or pinned `pyproject.toml`/`requirements.txt`; pin exact versions if it has none. Install them in the builder stage.
6. Make the agent's modules importable at `/app/agent_source` (the scaffold sets `PYTHONPATH` to it; add `/app/agent_source/src` for `src/` layouts).

Report the provider/model as whatever the agent is configured to use; `InvokeResponse.provider`/`model` may become framework metadata or be removed if the contract does not need them.

## Google ADK

Detect: `google-adk` dependency, `from google.adk`, a package exposing `root_agent` (usually `<agent>/agent.py` with `<agent>/__init__.py` importing it).

- Runner: `AGENT_MODULE=<package>.agent`. Uses `Runner.run_async` and returns the final response text.
- Model auth: Gemini API key (`GOOGLE_API_KEY`, `GOOGLE_GENAI_USE_VERTEXAI=FALSE`) or Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and Application Default Credentials). For Vertex, ask how the container gets credentials (workload identity, mounted service-account file, or none locally). Never bake a key file into the image.
- Non-Gemini models via `LiteLlm` need that provider's key.
- Sessions: `InMemorySessionService` loses state per request/restart. If the agent needs conversation continuity, ask where sessions should live (`DatabaseSessionService` with a DB URL, or `VertexAiSessionService`), and accept a `session_id` in the request contract.
- Artifacts/memory services (GCS, Vertex memory bank) are data stores; ask about them.
- Alternative transport: ADK's own `get_fast_api_app` / `adk api_server` exposes ADK's API rather than the agreed contract. Use it only if the user wants ADK's native API.
- If the user wants Cloud Run, GKE, or Agent Runtime instead of Docker/microVM, hand off to the `google-agents-cli-deploy` skill.

## CrewAI

Detect: `crewai` dependency, `@CrewBase` class in `crew.py`, `config/agents.yaml` and `config/tasks.yaml`, `main.py` calling `kickoff(inputs=...)`.

- Runner: `CREW_CLASS=<package>.crew:<CrewClass>`. Builds a fresh crew per request and runs `kickoff(inputs=...)` in a thread pool; returns `CrewOutput.raw`. Inputs must be an object whose keys match the `{placeholders}` in the YAML task/agent definitions; make the request schema list those keys.
- Model: set per agent in YAML or `LLM(...)`, often via `MODEL` plus the provider key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, ...). Read the YAML to find which providers are actually used.
- Tools commonly need their own keys (e.g. `SERPER_API_KEY` for `SerperDevTool`); every tool key is a required question.
- `memory=True`, knowledge sources, and RAG tools write local stores (embeddings DB, SQLite) and call an embedding provider. Ask whether that state must persist; if so, mount a volume and point the storage directory at it, otherwise run with a read-only root and a tmpfs.
- Crews can run for minutes. If runs exceed an HTTP timeout, switch the contract to a job ID + polling endpoint with a durable job store.
- CrewAI sends anonymous telemetry by default. Ask whether it must be disabled, then set the opt-out variable documented for the pinned version.

## Claude Agent SDK ("Anthropic harness")

Detect: `claude-agent-sdk` (Python, `from claude_agent_sdk import ...`) or `@anthropic-ai/claude-agent-sdk` (TypeScript), `ClaudeAgentOptions`, `query(...)` or `ClaudeSDKClient`.

- The Python wheel bundles a native Claude Code CLI for the target platform, so the Python image needs no Node. A TypeScript agent needs a Node base image instead of the Python template; keep the same endpoints and hardening.
- Runner: `AGENT_OPTIONS_FACTORY=<module>:<function>` returning the agent's `ClaudeAgentOptions`. If the source builds options inline, extract them into a factory. The runner streams `query()` and returns `ResultMessage.result`.
- Auth: `ANTHROPIC_API_KEY`, or Bedrock (`CLAUDE_CODE_USE_BEDROCK=1` + AWS credentials) or Vertex (`CLAUDE_CODE_USE_VERTEX=1` + GCP credentials). Ask which.
- **Tools are the main risk.** Built-in tools include `Bash`, `Write`, `Edit`, `WebFetch`. Keep the source's `allowed_tools`; if it allows `Bash`/`Write`, require an isolated working directory, a non-root user, and recommend the microVM runtime. Never set `permission_mode="bypassPermissions"` without explicit user approval. Use `max_turns` and `max_budget_usd` to bound each request.
- MCP servers in `mcp_servers` are external services: each needs its URL/command, credentials, and an egress rule.
- Sessions and settings live under the user's home (`~/.claude`). If `resume`/`continue_conversation` is part of the contract, mount a persistent volume for HOME; otherwise keep it on tmpfs. Set `setting_sources` explicitly so host settings are never picked up.
- For plain Anthropic SDK agents (`anthropic` package, tool runner or a manual tool loop), wrap the agent's entry function the same way and treat each tool as an adapter.

## Questions the scan cannot answer

Ask about these even when the scan found references, because the code shows that a store exists, not where it lives:

- connection target per data store (managed service, host, another container, or none for a local run), network path from the container/microVM, and read-only vs read-write
- whether a store holds personal, regulated, or production data, and whether a test/dev instance should be used for verification
- for each credential: who issues it, how it reaches the container at runtime (environment, secret manager, `sbx secret`), and whether a sandbox/test key exists
- vector stores and their embedding model/provider, which may differ from the chat model
