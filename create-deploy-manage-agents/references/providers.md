# Provider configuration

Use the exact model chosen by the user. Do not silently swap models or providers.

| Provider choice | Runtime value | Credential | Optional endpoint |
|---|---|---|---|
| Gemini | `gemini` | `GEMINI_API_KEY` | `GEMINI_BASE_URL` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `OPENAI_BASE_URL` |
| Anthropic Claude | `anthropic` | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` |
| Ollama | `ollama` | none by default | `OLLAMA_BASE_URL` |

Shared settings:

- `LLM_PROVIDER`: one of the runtime values above
- `LLM_MODEL`: exact provider model identifier
- `MODEL_TIMEOUT_SECONDS`: strict request deadline
- `MAX_OUTPUT_TOKENS`: output ceiling
- `MAX_INPUT_CHARS`: transport-level input ceiling

Keep credentials server-side. Never accept provider keys in the agent request payload. Redact authorization headers, query keys, raw prompts, attachments, and sensitive model output from logs.

The bundled baseline uses direct HTTPS APIs so one image can support all four providers. If the target skill needs provider-native tool calling, files, embeddings, batch APIs, or streaming, replace only the model gateway with the official SDK and pin its dependency.

For Ollama, confirm the requested model exists before a live test. Do not pull a model without user approval because downloads can be large. A container reaching host Ollama usually uses `http://host.docker.internal:11434`; Linux may require `--add-host=host.docker.internal:host-gateway`.

