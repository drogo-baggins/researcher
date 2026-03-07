# Proposal: Add OpenAI-Compatible Provider Support

## Change ID
`add-openai-compatible-providers`

## Summary
Extend LLM support beyond Ollama to allow users to configure any number of
OpenAI-compatible providers (VeniceAI, Azure OpenAI, OpenAI itself, etc.)
with a custom `base_url` and `api_key`.

## Motivation
The current system only supports local Ollama inference.  Many users also want
to use cloud providers (VeniceAI, Azure OpenAI, OpenRouter, etc.) that expose
an OpenAI-compatible REST API.  Supporting these providers with zero-friction
configuration is essential for broader adoption.

## What Changes

### New capability: OpenAI-compatible provider registry
- Users can register multiple providers in Settings, each with:
  - `name` – display label (e.g. "VeniceAI", "Azure OpenAI")
  - `base_url` – API endpoint (e.g. `https://api.venice.ai/api/v1`)
  - `api_key` – bearer token (stored in settings.json; not shown in clear text in UI)
  - `models` – manually entered list of model IDs available on that provider
- Providers are stored in `~/.researcher/settings.json` under the key `llm_providers`

### New module: `openai_compat_client.py`
- Implements the same interface as `OllamaClient`
  (`generate_response`, `generate_response_stream`, `get_embeddings`, `test_connection`, `list_models`)
- Uses `httpx` (already a dependency) to call the provider's chat-completions and
  embeddings endpoints

### Updated Settings page (3_⚙️_Settings.py)
- New "🌐 LLMプロバイダ" section: add / edit / remove provider entries
- Per-provider model list (manually entered IDs, comma-separated)
- Model selector for search/response/eval now shows
  `provider::model_id` as the canonical key

### Updated config.py
- `load_settings` / `save_settings` handle `llm_providers` list
- New helper `build_llm_client(model_key)` factory that parses
  `provider::model_id` and returns the right client instance

### Updated ChatManager, QueryAgent, Reranker
- Accept a generic `llm_client` (duck-typed) instead of `OllamaClient`

## Impact
- **Backward compatible**: if no OpenAI providers are configured, Ollama flow
  is unchanged; existing `search_model` / `response_model` / `eval_model`
  settings that contain plain model names (no `::`) continue to resolve via Ollama.
- No database migration needed.
- No new required dependencies (`httpx` already in the transitive tree via `ollama`).

## Out of Scope
- OAuth / multi-step authentication flows
- Automatic model discovery from provider API
- Streaming token-level usage tracking per provider
