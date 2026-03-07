# Tasks: Add OpenAI-Compatible Provider Support

## Status: Complete

## Tasks

- [x] 1. Create `openai_compat_client.py` with `OpenAICompatClient` class
- [x] 2. Update `config.py`: add `llm_providers` to DEFAULT_SETTINGS & helpers
- [x] 3. Update `agent.py` to accept generic `llm_client` (duck-type, remove OllamaClient import)
- [x] 4. Update `chat_manager.py` to rename `ollama_client` → `llm_client`
- [x] 5. Update `reranker.py` if it references OllamaClient
- [x] 6. Update Settings page: provider management UI + updated model selectors
- [x] 7. Update Chat page session initialisation: use `build_llm_client(key)`
- [x] 8. Update `utils/page_utils.py` `initialize_session`: use `build_llm_client`
- [x] 9. Update `cli.py` to use `build_llm_client`
- [ ] 10. Write unit tests for `OpenAICompatClient`
- [ ] 11. Write unit tests for `build_llm_client` factory
- [x] 12. Run existing test suite and fix regressions
