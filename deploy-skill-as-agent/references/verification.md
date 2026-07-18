# Verification checklist

## Source and contract

- The copied skill matches the resolved local path or Git commit.
- Provenance records repository URL, resolved commit/ref, and subdirectory when applicable.
- The suitability report covers tools, dependencies, side effects, state, credentials, and licenses.
- Request, response, and error models match the user's examples.
- Every behavior promised by the source skill has a runtime capability or an explicit limitation.

## Application

- Configuration fails clearly when the selected provider or credential is missing.
- Unit tests use a fake model gateway and make no network calls.
- Tests cover success, invalid input, provider failure, malformed structured output, and adapters.
- Logs contain correlation fields and no credentials or raw sensitive payloads.
- Timeouts, retries, tool calls, input size, and output size are bounded.

## Container

- `docker build` succeeds from a clean package.
- The final process runs as non-root with an exec-form command.
- `.dockerignore` excludes secrets, VCS data, caches, tests, and local environments.
- `/healthz` succeeds without contacting the provider.
- The container stops within the grace period.
- Required state lives in an explicit volume or external store, not the disposable layer.

## Provider smoke test

- The selected key is supplied through the environment, never a file copied into the image.
- One minimal request succeeds using the exact chosen model, or is explicitly reported as unverified.
- Usage/error metadata is recorded without exposing sensitive request data.

