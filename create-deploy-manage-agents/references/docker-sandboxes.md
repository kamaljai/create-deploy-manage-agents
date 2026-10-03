# Docker Sandboxes (microVM) runtime

Use this reference only when the user chose the **Docker microVM** runtime. Docker Sandboxes (`sbx` CLI) run each sandbox in its own lightweight microVM with a private Docker engine, so the agent container gets a VM boundary instead of sharing the host kernel.

## Approach

Reuse the same generated Dockerfile and image. Do not write a second packaging path:

1. Create a `shell` sandbox with the package directory mounted read-only.
2. Build the image with the sandbox's private Docker engine.
3. Run the container inside the sandbox and publish its port to host loopback with `sbx ports`.

The generated `deploy/microvm.sh` does exactly this. Read it, adapt it to the agreed contract, and keep it the single documented entrypoint for this runtime.

Do not convert the package into a sandbox kit unless the user asks. Kits (`# syntax=docker/sandbox-kit:3`) are experimental; if one is requested, follow the authoritative spec at https://github.com/docker/sandbox-kit-spec and do not invent descriptor fields.

## Prerequisites

Check before generating microVM instructions and report anything missing:

- `sbx version` succeeds. Install from https://www.docker.com/products/docker-sandboxes if not.
- `sbx login` has been completed by the user. Never run login on the user's behalf; suggest `! sbx login`.
- `sbx diagnose` reports no blocking problems.
- Host support: macOS on Apple silicon or Windows/Linux with hardware virtualization. If unsupported, fall back to the plain Docker runtime and say so.

## Commands (verified against `sbx` v0.45)

```bash
sbx create --name <name> shell <package-dir>:ro   # microVM with read-only workspace
sbx exec <name> docker build -t <image> <package-dir>
sbx exec -e LLM_PROVIDER -e LLM_MODEL -e <KEY_VAR> <name> \
  docker run -d --name agent --read-only --tmpfs /tmp -p 8080:8080 \
  -e LLM_PROVIDER -e LLM_MODEL -e <KEY_VAR> <image>
sbx ports <name> --publish 127.0.0.1:<host-port>:8080
sbx ports <name>                                   # list published ports
sbx policy ls                                      # inspect egress rules
sbx policy log                                     # see blocked requests
sbx stop <name>                                    # keep state
sbx rm <name>                                      # destructive; confirm first
```

Nested `--help` output varies across `sbx` releases. Confirm exact flags for `sbx policy allow` and `sbx secret set` with the installed version before writing them into the package; do not guess.

## Credentials

- Pass the provider key to `sbx exec -e KEY` and from there to `docker run -e KEY`, taking the value from the caller's environment. Do not pass it to `sbx create`, which stores it in the sandbox spec.
- `sbx secret set <service>` lets the sandbox proxy authenticate supported services without exposing the key inside the VM. The baseline config requires the key variable, so adopting proxy injection needs a deliberate config change and a live test. Offer it, but do not claim it works untested.

## Networking

- Sandbox egress is policy-controlled. The build needs the Python base image registry and PyPI; runtime needs only the selected provider's API host. Inspect `sbx policy log` when a build or model call fails, and add the narrowest allow rule after the user approves it.
- Ollama on the host: `host.docker.internal` from a container nested in a microVM may not reach the host. Verify reachability with `sbx exec <name> curl -fsS <OLLAMA_BASE_URL>/api/tags` before a live test, and report it as unverified when it fails.
- Published ports bind to loopback by default. Bind a non-loopback address only when the user explicitly asks to expose the service.

## Cloud sandboxes

`sbx --cloud` runs sandboxes in Docker's cloud. That publishes workloads off the user's machine, costs money, and exposed ports get public URLs. Use it only after separate explicit approval, and treat it as a deployment, not a local run.
