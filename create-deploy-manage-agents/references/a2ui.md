# A2UI web UI

Use this reference when the user wants a UI (`--ui a2ui`). [A2UI](https://a2ui.org/) is a declarative protocol: the agent sends JSON describing UI built from a client-approved component catalog, and the client renders it with native components. No agent-supplied code runs in the browser.

## What the template provides (verified with `@a2ui/lit` 0.12.0, protocol v0.9)

- `src/skill_agent/a2ui.py`: builds a task surface with the **basic catalog** (`https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json`). It contains a title, one `TextField` per entry in `FORM_FIELDS` bound to `/input/<name>`, a **Run task** `Button` whose `run_task` event carries the field values, and `status`/`result` `Text` components bound to the data model.
- `GET /a2ui/surface` returns `createSurface`, `updateComponents`, and `updateDataModel` messages.
- `POST /a2ui/action` accepts `{"version": "v0.9", "action": {...}}` and streams JSON lines: a running status first, then the result and the final status. Unknown actions and empty input never reach the agent.
- `ui/`: a Vite + TypeScript client. It uses `MessageProcessor` from `@a2ui/web_core/v0_9` and the `<a2ui-surface>` element from `@a2ui/lit/v0_9`, with sanitized Markdown from `@a2ui/markdown-it` (DOMPurify). The Dockerfile builds it in a Node stage and the agent serves it at `/ui`.

The template uses REST plus streamed JSON lines, one of the transports the spec lists, so it needs no extra Python dependency and works for every source kind. Actions go through `AgentService.invoke`, so once a framework runner is wired in, the UI drives ADK, CrewAI, and Claude Agent SDK agents unchanged.

## Adapting it

1. Set `FORM_FIELDS` to one entry per request property, using TextField variants `shortText`, `longText`, `number`, or `obscured`. A single field named `input` is sent as `InvokeRequest.input`, parsed as JSON when valid. Several fields are sent as an object.
2. For structured output, replace `_render_output` with components (`Card`, `List`, `Row`) plus `updateDataModel` messages instead of one Markdown string. Build them on the server from validated output. Never forward model-authored component JSON without validating it against the catalog.
3. For multi-step or approval tasks, add named actions (for example `approve_step`) with explicit handlers. Each handler must validate its context and enforce the same policy checks as the API.
4. Keep `catalogId` equal to the client's `basicCatalog.id`. Add a custom catalog only when the user needs components the basic catalog lacks, and register it on both sides.

## LLM-generated UI (optional)

If the user wants the agent itself to compose UI, as with generative UI, use the official `a2ui-agent-sdk` Python package (`A2uiSchemaManager` for catalog prompts, plus its parser and validator). For ADK agents, use `SendA2uiToClientToolset`. It pulls in `google-adk` and `a2a-sdk`, so add it only when this is requested. Validate every generated payload before streaming it, and keep the fixed task form as a fallback.

## A2A or AG-UI transports

The spec also defines A2UI over the A2A extension (MIME type `application/a2ui+json`) and AG-UI/CopilotKit (`@copilotkit/a2ui-renderer`). Use one only when the user's client already speaks it; otherwise keep the bundled REST client.

## Security

- The UI and the API have no authentication. Keep the published port on loopback (the default for `sbx ports`; use `-p 127.0.0.1:8080:8080` for Docker), or put an authenticating proxy in front before exposing it.
- Treat action `context` as untrusted user input; it is size-limited and validated through `InvokeRequest`.
- Error details stay in server logs. The UI shows a generic failure message.

## Local UI development

```bash
cd ui && npm ci && npm run dev   # Vite dev server; proxies /a2ui to the agent on :8080
```
