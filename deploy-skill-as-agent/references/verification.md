# Verification checklist

## Source and contract

- The copied skill matches the resolved local path or Git commit.
- Provenance records repository URL, resolved commit/ref, and subdirectory when applicable.
- The suitability report covers tools, dependencies, data stores, side effects, state, credentials, and licenses.
- For an agent source, provenance records the source kind and the runner targets the confirmed entrypoint.
- Request, response, and error models match the user's examples.
- Every behavior promised by the source skill has a runtime capability or an explicit limitation.

## Application

- Configuration fails clearly when the selected provider, a required credential, or a data-store setting is missing.
- `.env.example` lists every confirmed credential and data-store variable with placeholders only.
- Agent tool permissions are no wider than the source's; shell/file tools run in a dedicated workdir.
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
- Each data store is reachable from the container (or microVM) on its confirmed path; verification used a test instance or had explicit approval.

## Docker microVM runtime (only when chosen)

- `sbx version` and `sbx diagnose` succeed; the user has completed `sbx login`.
- `deploy/microvm.sh` creates the sandbox with the package mounted read-only and builds the image inside it.
- `/healthz` succeeds on the published loopback port.
- No credential appears in the sandbox spec (`sbx create` receives no key) or in script output.
- Egress denials seen in `sbx policy log` are resolved with the narrowest approved rule or reported.
- `sbx stop` stops the sandbox; removal is left to the user unless approved.

## Provider smoke test

- The selected key is supplied through the environment, never a file copied into the image.
- One minimal request succeeds using the exact chosen model, or is explicitly reported as unverified.
- Usage/error metadata is recorded without exposing sensitive request data.

