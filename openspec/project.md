# Project Context

## Purpose

**researcher** is a Perplexity-style local search AI system that combines:
- Local LLM inference (Ollama) for privacy and speed
- Intelligent web search (SearXNG) with automatic query detection
- Citation-based answers with reliability scoring
- MCP (Model Context Protocol) integration for system tools
- Multi-language support (Japanese/English)

**Goals:**
- Provide a fully local, privacy-preserving alternative to cloud-based AI search
- Automatically determine when web search is needed for current information
- Generate accurate, cited responses with source attribution
- Enable LLM integration with local system resources (files, calendar, notes)
- Support both CLI and web-based UI workflows

## Tech Stack

**Core Technologies:**
- **Python 3.8+**: Primary language
- **Ollama**: Local LLM inference (llama3, mixtral, etc.)
- **SearXNG**: Meta-search engine (Docker deployment)
- **Streamlit**: Web UI framework
- **SQLite**: Session/conversation storage

**Key Libraries:**
- `ollama>=0.6.0`: LLM client
- `requests>=2.31.0`: HTTP client
- `beautifulsoup4>=4.12.0`: Web scraping
- `lxml>=4.9.0`: HTML/XML parsing
- `streamlit>=1.38.0`: Web interface
- `mcp>=1.0.0`: Model Context Protocol
- `python-dateutil>=2.8.0`: Date/time handling

**Development Tools:**
- `pytest>=7.0.0`: Testing framework
- `pytest-playwright>=0.4.0`: E2E testing
- `playwright>=1.40.0`: Browser automation

**Infrastructure:**
- Docker (for SearXNG)
- Shell scripts for automation (setup.sh, run.sh, deploy.sh)

## Project Conventions

### Code Style

**Python Conventions:**
- Follow PEP 8 style guidelines
- Use type hints where applicable (`Optional`, `Dict`, `List`, etc.)
- Class names: PascalCase (e.g., `ChatManager`, `OllamaClient`)
- Function/variable names: snake_case (e.g., `add_user_message`, `auto_search`)
- Constants: UPPER_SNAKE_CASE (e.g., `DEFAULT_SEARXNG_URL`)
- Private methods: prefix with underscore (e.g., `_internal_method`)

**File Organization:**
- Core modules in `src/researcher/`
- Tests in `tests/` (mirror source structure)
- Documentation in `docs/`
- Config/setup scripts in project root
- Streamlit pages in `src/researcher/pages/`

**Naming Patterns:**
- Clients: `*Client` (e.g., `OllamaClient`, `SearXNGClient`)
- Managers: `*Manager` (e.g., `ChatManager`, `SessionManager`)
- Configuration files: Use lowercase with underscores (e.g., `mcp_config.json`)

### Architecture Patterns

**Core Patterns:**
1. **Manager Pattern**: Central `ChatManager` orchestrates all components
2. **Client Pattern**: Separate clients for external services (Ollama, SearXNG, MCP)
3. **Agent Pattern**: `QueryAgent` for intelligent query analysis and search decisions
4. **Session Management**: SQLite-based conversation history with CRUD operations
5. **Citation System**: Track and display sources with reliability scoring

**Component Structure:**
```
ChatManager (orchestrator)
├── OllamaClient (LLM inference)
├── SearXNGClient (web search)
├── WebCrawler (content extraction)
├── Reranker (result ranking)
├── CitationManager (source tracking)
├── MCPClient (system tools)
└── SessionManager (persistence)
```

**Data Flow:**
1. User query → ChatManager
2. QueryAgent analyzes if search needed
3. If needed: SearXNG → WebCrawler → Citations
4. Context building with search results
5. OllamaClient generates response
6. SessionManager persists conversation

**Configuration Strategy:**
- Multi-level config resolution: CLI args > Environment vars > Defaults
- Runtime config stored in `~/.researcher/config.json`
- Persistent data in `~/.researcher/` (sessions.db, feedback.json, blacklist.json)

### Testing Strategy

**Test Categories (pytest markers):**
- `integration`: Tests requiring Ollama server
- `e2e`: End-to-end tests with Playwright (require running services)
- Default: Unit tests (no external dependencies)

**Test Organization:**
- `tests/test_*.py`: Unit and integration tests
- `tests/e2e/`: End-to-end Streamlit UI tests
- Mirror source structure: `test_chat_manager.py` ↔ `chat_manager.py`

**E2E Testing:**
- Use Playwright for browser automation
- Test complete user workflows in Streamlit UI
- Verify session persistence and UI state management
- E2E tests skipped by default (run with `-m e2e`)

**Testing Best Practices:**
- Mock external services for unit tests
- Use fixtures for common setup (sessions, configs)
- Test error handling and edge cases
- Verify data persistence and state management

### Git Workflow

**Branching:**
- `main`: Production-ready code
- Feature branches: Descriptive names (e.g., `feature/settings-page`, `fix/tag-persistence`)

**Commit Conventions:**
- Use descriptive commit messages
- Examples from history:
  - "Update researcher project with settings page and improvements"
  - "Add E2E test setup and documentation"
  - Clear, concise descriptions of changes

**Repository:**
- Private GitHub repository: `drogo-baggins/researcher`
- Uses GitHub CLI (`gh`) for repository management

## Domain Context

**AI Research Assistant Domain:**
- **Perplexity-style Search**: Combination of LLM + web search with citations
- **Local-first Philosophy**: Privacy, no cloud dependencies, full control
- **Intelligent Search Triggering**: Automatic detection of queries needing current information
- **Citation-based Answers**: Track sources, provide reliability scores
- **Multi-modal Context**: Combine web search, LLM knowledge, and system tools (MCP)

**Key Concepts:**
- **Auto-search**: Automatic detection when queries need web lookup vs LLM knowledge
- **Reranking**: Re-order search results by relevance using embeddings
- **Citation Reliability**: Score sources based on domain authority and content quality
- **Session Persistence**: Save/restore conversation history across sessions
- **MCP Integration**: Allow LLM to access local files, calendar, notes via Model Context Protocol

**User Workflows:**
1. **CLI Mode**: Terminal-based Q&A with automatic search
2. **WebUI Mode**: Browser-based interface with session management
3. **Research Mode**: Deep search with multiple sources and citations
4. **Local Knowledge**: Pure LLM responses without web search

## Important Constraints

**Privacy & Security:**
- **Local-only execution**: No cloud API dependencies
- **No authentication**: WebUI designed for single-user local access only
- **Plaintext storage**: Session data in SQLite without encryption
- **Localhost binding**: WebUI only accessible from `localhost:8501`
- **MCP filesystem access**: LLM can access files via MCP (security consideration)

**Technical Constraints:**
- Python 3.8+ required (modern type hints, async features)
- Requires Ollama installation and running service
- SearXNG requires Docker (optional but recommended)
- SQLite for data persistence (lightweight, embedded)
- Streamlit single-threaded model (state management considerations)

**Resource Constraints:**
- LLM inference depends on local hardware (GPU recommended)
- Web crawling rate-limited to avoid overwhelming sites
- Embedding models require RAM (especially for large models)
- Session database grows with conversation history

**Operational Constraints:**
- Designed for single-user personal use
- Not suitable for multi-tenant or production web deployment
- No built-in rate limiting or quota management
- Requires manual setup of external services (Ollama, SearXNG)

## External Dependencies

**Required Services:**
1. **Ollama** (`http://localhost:11434`)
   - Purpose: Local LLM inference
   - Models: llama3, mixtral, phi, etc.
   - Installation: https://ollama.com
   - Required for all functionality

2. **SearXNG** (`http://localhost:8888`)
   - Purpose: Meta-search engine (aggregates Google, Bing, etc.)
   - Deployment: Docker container
   - Configuration: `searxng_settings.yml`
   - Optional but enables web search features

**Optional MCP Servers (Node.js-based):**
- **filesystem**: File system access for LLM
- **notes**: Apple Notes integration
- **calendar**: iCal/calendar access
- Configuration: `~/.researcher/mcp_config.json`

**Python Package Dependencies:**
- See `pyproject.toml` for complete list
- All installable via pip/uv
- No complex C dependencies (pure Python where possible)

**System Requirements:**
- macOS/Linux (primary targets)
- Shell environment (bash/zsh)
- Docker (for SearXNG)
- Node.js (for MCP servers, optional)

**Data Storage Locations:**
- `~/.researcher/config.json`: Runtime configuration
- `~/.researcher/sessions.db`: SQLite conversation history
- `~/.researcher/feedback.json`: User feedback data
- `~/.researcher/blacklist.json`: URL blacklist

## Quality Assurance Requirements

**MANDATORY UI VALIDATION:**

**All code changes that affect user-facing functionality MUST include comprehensive UI validation before being considered complete. This is a non-negotiable requirement.**

**Required validation steps:**
1. **E2E Testing**: Execute Playwright tests or equivalent automated UI tests
2. **Manual Testing**: Verify all affected UI components work correctly
3. **Issue Resolution**: Fix ALL detected UI problems, broken workflows, or test failures
4. **Documentation**: Record test results in proposal tasks.md or relevant documentation

**When UI validation is required:**
- Any change to Streamlit pages (`src/researcher/pages/`)
- Changes to UI utilities (`src/researcher/utils/page_utils.py`)
- Configuration changes affecting UI behavior
- New features with user-facing components
- Bug fixes for UI issues

**Validation checklist:**
- [ ] Streamlit app starts without errors
- [ ] All pages are accessible and render correctly
- [ ] User workflows complete successfully
- [ ] Error messages display appropriately
- [ ] Settings changes take effect
- [ ] E2E tests pass
- [ ] No console errors or warnings

**Implementation is NOT complete until:**
- All E2E tests pass
- Manual testing confirms no UI issues
- All detected problems are resolved
- Test results are documented

**This requirement applies to all OpenSpec change proposals affecting UI.**
