---
name: deploy-skill-as-agent
description: Convert a local Codex/agent skill or a skill stored in a GitHub repository into a runnable, provider-flexible LLM agent packaged for Docker. Use when a user asks to containerize, serve, deploy, expose through HTTP or CLI, or turn a SKILL.md-based capability into an agent using Gemini, Ollama, OpenAI, or Anthropic Claude. Gather the source skill, model provider, and exact input/output contract; assess portability and safety before generating code; decline or explain remediation when the skill cannot be safely or faithfully deployed this way.
---

# Deploy a skill as an agent

Produce a complete deployment package, not only a Dockerfile or architecture description. Keep secrets out of source, images, logs, and committed environment files.

## 1. Gather the required contract

Before inspecting or generating code, ask for all missing items in one concise message:

1. **Skill source:** local installed skill name/path, or GitHub repository URL plus optional ref and subdirectory.
2. **LLM provider:** Gemini, Ollama, OpenAI, or Anthropic Claude, including the model name. For Ollama, also ask whether it runs on the Docker host or in a separate service.
3. **Input:** transport (`HTTP`, `CLI`, or both), payload shape, required fields, attachments, size limits, and one representative example.
4. **Output:** response shape or MIME type, required fields, error behavior, destination, and one representative example.

Ask whether the user wants package artifacts only or an actual deployment if deployment is mentioned. Do not deploy or publish without separate explicit approval.

If the source or I/O contract is still ambiguous, pause generation and resolve it. Do not infer a materially different interface.

## 2. Resolve and inspect the source

For a local name, search the configured skill roots, project `.agents/skills` and `.codex/skills`, and explicit user paths. Require exactly one match.

For GitHub:

- Resolve the exact repository, ref, and skill subdirectory.
- Use existing authenticated access for private repositories; never request a token in chat or put one in a URL.
- Clone or download into a temporary directory and pin the resolved commit in the generated package metadata.
- Review files before executing any source script.

Read the complete source `SKILL.md`. Follow its direct links to required references, scripts, and assets. Inventory runtimes, package dependencies, external tools, connectors, network services, credentials, side effects, licenses, and host assumptions.

Run `scripts/assess_skill.py <skill-directory>` for a repeatable inventory, then apply the judgment rules in [references/suitability.md](references/suitability.md). The scan is evidence, not an automatic approval.

## 3. Make a suitability decision

Classify the source before scaffolding:

- **Suitable:** instruction/reference skill can run through an LLM with the requested interface.
- **Suitable with adaptations:** scripts or remote tools can be exposed through bounded, typed adapters without changing the promised behavior.
- **Not suitable:** faithful operation depends on unavailable Codex UI/tooling, interactive desktop control, undeployable local state, unsupported runtimes, unclear rights, or unsafe side effects without an approval/control plane.

Tell the user the classification and its concrete reasons. For adaptations, state what will change and obtain confirmation when it changes behavior, cost, privacy, or external side effects. For an unsuitable skill, stop and offer specific remediation; do not emit a misleading prompt-only wrapper.

## 4. Design the smallest faithful agent

Read [references/package-contract.md](references/package-contract.md) before implementation and [references/providers.md](references/providers.md) for the selected provider.

Use a synchronous request service for short work. Add a queue and durable job store only when the contract includes long-running, retryable, scheduled, or restart-safe work.

Keep these boundaries even in a small package:

- transport and input validation
- agent/application service
- model gateway
- typed tool adapters
- configuration and secret loading
- structured telemetry
- output validation

Do not let the model execute arbitrary shell commands or choose arbitrary file paths. Wrap required source scripts as explicit allowlisted functions with validated arguments, fixed working directories, timeouts, output limits, and least privilege. Put destructive, financial, security-sensitive, or public actions behind deterministic policy checks and explicit approval.

## 5. Scaffold and adapt the package

Start from the bundled template:

```bash
python scripts/scaffold_agent.py \
  --name <agent-name> \
  --skill-dir <resolved-skill-directory> \
  --output-dir <new-empty-directory> \
  --provider <gemini|ollama|openai|anthropic> \
  --model <exact-model-name> \
  --transport <http|cli|both> \
  --input-description '<concise contract>' \
  --output-description '<concise contract>'
```

The script refuses to overwrite a non-empty directory. It copies the source skill, records provenance, substitutes package settings, and creates a provider-flexible Python/Docker baseline.

Then adapt the generated package:

1. Replace the generic request and response models with explicit Pydantic types matching the agreed examples.
2. Include only source references needed at runtime; exclude unrelated, secret, cached, generated, or licensed-prohibited files.
3. Add typed adapters for every required source script or external service. Never rely on a skill instruction that names a tool the runtime does not actually provide.
4. Parse and validate structured model output before returning or taking action. Retry malformed output at most once with a corrective prompt.
5. Add durable state, idempotency, bounded retries, and a queue only when required by the contract.
6. Update generated tests to cover the real input/output schema and any adapters.
7. Keep `.env.example` to variable names and safe placeholders. Inject real keys only at runtime.

For Ollama on the host, use `host.docker.internal` on Docker Desktop and document the Linux host-gateway alternative. Add an Ollama Compose service only when the user explicitly wants Ollama managed with the package; model downloads are operational steps and may be large.

## 6. Verify before handoff

Run every applicable check in [references/verification.md](references/verification.md). At minimum:

1. Validate the source copy and generated provenance.
2. Run formatting/static checks and unit tests with a fake model gateway.
3. Build the Docker image.
4. Run the container without real credentials on its deterministic health path.
5. If credentials are available through the environment and the user authorizes usage, run one minimal live request; never print the key.
6. Stop the container gracefully and inspect the final diff.

If Docker, provider access, or another prerequisite is unavailable, finish safe source work and state exactly which verification remains. Never claim the original skill was faithfully converted if required tools or behaviors were omitted.

## 7. Hand off

Lead with what works and include:

- package location and source skill commit/path
- suitability result and adaptations made
- exact test and container results
- required environment variable names
- exact build and run commands
- request/response example using the agreed contract
- deliberate limitations and any unverified live-provider step

