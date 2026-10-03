# __AGENT_NAME__

Dockerized LLM agent generated from a packaged skill.

- Default provider: `__DEFAULT_PROVIDER__`
- Default model: `__DEFAULT_MODEL__`
- Transport: `__TRANSPORT__`
- Input contract: __INPUT_DESCRIPTION__
- Output contract: __OUTPUT_DESCRIPTION__

Review `skill-provenance.json` and the copied `skill_source/` before building. Replace the generic request/response models in `src/skill_agent/schemas.py` with the agreed contract and implement every required tool adapter.

## Local checks

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
```

## Run locally

Set `LLM_PROVIDER`, `LLM_MODEL`, and the selected provider credential in your shell. Ollama normally uses `OLLAMA_BASE_URL` instead of a key.

```bash
uvicorn skill_agent.api:app --host 0.0.0.0 --port 8080
python -m skill_agent.cli --input '{"example":"replace with the agreed input"}'
```

## Docker

```bash
docker build -t __AGENT_SLUG__:local .
docker run --rm --read-only --tmpfs /tmp \
  -p 8080:8080 \
  -e LLM_PROVIDER \
  -e LLM_MODEL \
  -e GEMINI_API_KEY \
  -e OPENAI_API_KEY \
  -e ANTHROPIC_API_KEY \
  -e OLLAMA_BASE_URL \
  __AGENT_SLUG__:local
```

Pass only the credential for the selected provider. Do not put real keys in `.env.example` or the image.

```bash
curl -fsS http://localhost:8080/healthz
curl -fsS -X POST http://localhost:8080/v1/invoke \
  -H 'content-type: application/json' \
  -d '{"input":{"example":"replace with the agreed input"}}'
```


<!-- @ui-begin -->
## A2UI web UI

The agent serves an [A2UI](https://a2ui.org/) v0.9 interface at `http://localhost:8080/ui`. It renders a task form with the `@a2ui/lit` basic catalog; **Run task** sends an A2UI `action` to `POST /a2ui/action`, and the agent streams `updateDataModel` messages (status, then result) back as JSON lines. `GET /a2ui/surface` returns the initial `createSurface` / `updateComponents` / `updateDataModel` messages.

Edit `FORM_FIELDS` in `src/skill_agent/a2ui.py` to match the request contract. For UI development:

```bash
cd ui && npm ci && npm run dev   # proxies /a2ui to the agent on :8080
```

The UI has no authentication. Keep it on loopback, or put it behind an authenticating proxy before exposing it.
<!-- @ui-end -->
