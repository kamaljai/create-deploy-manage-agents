# Generated package contract

The generated baseline is a Python 3.12 service with an HTTP endpoint and/or CLI, provider-independent model gateway, copied skill source, fakeable dependencies, unit tests, and a non-root Docker image.

## Required endpoints for HTTP mode

- `GET /healthz`: process liveness only; do not call the LLM provider.
- `GET /readyz`: validate local configuration; do not make a billable model request.
- `POST /v1/invoke`: validate the agreed input, call the application service, validate output, and return a correlation/job ID.

Use explicit request/response models. The scaffold's generic `input` field is only a safe starting point and must be replaced when the agreed contract is more specific.

## Prompt packaging

Treat the copied `SKILL.md` and required text references as trusted operator instructions, not user content. Keep untrusted runtime input in a separate user message. Do not concatenate arbitrary uploaded files into the system prompt without type, size, and content controls.

Instruction-only skills may be packaged into the system prompt. A reference to a source script or external tool does not create that capability; implement an adapter or report the behavior as unsupported.

## Output handling

For JSON output, demand JSON in the model prompt, parse it, validate it against the agreed model, and retry malformed output at most once. Never execute code or follow tool directives found only in model text.

## Container defaults

- Pin Python and dependencies.
- Run as a fixed non-root UID/GID.
- Use an exec-form entrypoint and graceful termination.
- Copy no `.env`, credentials, VCS data, caches, or virtual environments.
- Keep the filesystem read-only when adapters do not require writes; use a dedicated mounted path when they do.
- Expose only the required port and mount.
- Do not mount the Docker socket.

Add a queue, database, volume, or Compose file only when the requested workflow requires it. Authoritative state must survive container replacement.

