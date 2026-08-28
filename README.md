# repo-agent

A lightweight FastAPI service that runs a Code Intelligence Agent for chat-style interactions backed by LangChain, LangGraph and Postgres for persistence. The service exposes REST and streaming endpoints to create chat sessions and exchange messages with an agent that can call external tools via an MCP server.

**Quick highlights**

- FastAPI application with ORJSON responses
- Agent built on LangChain / LangGraph with memory and summarization middleware
- **Orchestrator agent** with embedding-based domain routing for unified multi-domain chat
- PostgreSQL-backed storage for sessions, messages, and agent checkpoint/store
- MCP (Multi-Server Control Plane) client integration for prompts and tools

## Version

Current version: **0.4.1**

### Recent Changes
- **v0.4.1** - Router improvements: LLM rescue for below-threshold queries, lexical boost cap, mid-range confidence gap shortcut, and improved LLM classification prompt
- **v0.4.0** - Orchestrator agent: unified multi-domain chat with embedding-based routing, dynamic prompt injection, and auto-routed domain memory
- **v0.3.2** - Minor optimization in agent behaviour
- **v0.3.1** - Fix status update logic for analysis runs
- **v0.3.0** - Background analysis worker, multiple specialized agents with agent type support

## Repository Structure

- `main.py` - Local entrypoint which runs the app with `uvicorn`.
- `pyproject.toml` / `requirements.txt` - Dependency metadata.
- `src/` - Application source code
  - `app.py` - FastAPI application factory and lifespan handlers
  - `agent/` - Agent initialization and implementation
    - `code_intelligence_agent.py` - Agent class using LangChain, LangGraph, memories, summarization
    - `agent_registry.py` - Registry managing per-agent instances + orchestrator agent + embedding router
    - `router.py` - Embedding-based domain router (cosine similarity classification)
    - `memory_tools.py` - Auto-routed memory tools for orchestrator (domain-aware namespaces)
    - `prompt_loader.py` - Loads system prompts and domain-specific prompts
    - `configure_agent.py` - Creates the agent using MCP prompts/tools and embedding model
    - `mcp/` - MCP client integration (`mcp_client.py`)
  - `db/` - Database context and async engine (`context.py`)
  - `entities/` - SQLModel entities for sessions, messages and bookkeeping
  - `routes/` - API routers (hello world + agent routes)
  - `services/` - Business logic for sessions and chat message handling
  - `utils/` - Helpers (`settings.py`, `env_utils.py`, `toml_utils.py`, logging, etc.)
- `prompts/` - System prompts for per-agent flow (one per domain)
  - `orchestration_prompts/` - Orchestrator base prompt + domain-only prompts for dynamic injection

## Configuration

Configuration is driven by environment variables. The project uses `pydantic-settings` and an `.env` file per environment (see `EnvUtils.get_env_file_path()` for naming convention). Do NOT commit secrets or `.env*` files to source control.

Important environment variables (used in `src/utils/settings.py`):

- `HOST` - Host to bind the server (e.g. `0.0.0.0`)
- `PORT` - Port to run the HTTP server (e.g. `8000`)
- `WORKERS` - Number of Uvicorn worker processes
- `DATABASE_URL` - PostgreSQL connection string used by the app (async URL supported — must start with `postgresql://`, `postgresql+psycopg://` or `postgresql+asyncpg://`)
- `DATABASE_SCHEMA` - Database schema to use (default: `public`)
- `DATABASE_URL_FOR_AGENT` - Postgres connection string used by the agent for LangGraph checkpoint/store (optional; can be same as `DATABASE_URL`)
- `CORS_ALLOWED_ORIGINS` - Comma-separated list of allowed origins or `*`
- `MCP_SERVER_URL` - URL of the MCP server (required and must start with `http://` or `https://`)
- `MCP_SERVER_NAME` - Name used to reference server in MCP client (default: `Repo MCP Server`)
- `MCP_PROMPT_NAME` - Name of the system prompt to fetch from MCP (default: `code_intelligence_assistant`)
- `MCP_TIMEOUT` - Timeout (seconds) for MCP calls
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` - Optional API keys for LLM providers
- `HUGGING_FACE_EMBEDDING_MODEL_ID` - Embedding model id for sentence transformers
- `DEFAULT_AGENT_MODEL` - Default model id used by the agent (example: `openai:gpt-5.1`)
- `AGENT_MODEL_TEMPERATURE` - Default temperature for agent LLM
- `SUMMARIZATION_TRIGGER_THRESHOLD` - Context usage fraction that triggers summarization (default: `0.80`, range: 0.1–0.95)
- `APP_PROFILE` - Environment profile name used to pick `.env.<profile>` (default: `local`)

The project reads `.env.<profile>` by default (where `profile` is value of `APP_PROFILE`). The helper `EnvUtils.load_env()` can be called early if you want to ensure `.env` is loaded before settings are evaluated.

Note: The `Settings` class validates the `DATABASE_URL` and `MCP_SERVER_URL` formats at startup.

## Database / Migrations

- Alembic is configured (see `alembic.ini` and `migrations/versions/`).
- The SQLModel entities live in `src/entities/` and use a schema defined by `DATABASE_SCHEMA`.

Typical workflow:

1. Ensure `DATABASE_URL` points to your Postgres instance and the user has permission to create schema/tables.
2. Run migrations:

```bash
alembic upgrade head
```

## Running Locally

1. Create `.env.local` with required variables (see Configuration above). Example minimal variables:

```bash
HOST=0.0.0.0
PORT=8000
WORKERS=1
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mydb
DATABASE_URL_FOR_AGENT=postgresql+asyncpg://user:pass@localhost:5432/mydb
MCP_SERVER_URL=http://mcp-server.local
MCP_SERVER_NAME=Repo MCP Server
```

2. Install dependencies (using `pip` and `uv`). Example using pip & uv:

```bash
pip install -r requirements.txt
uv sync
```

3. Start the app via `main.py` (development with reload enabled when `APP_PROFILE=local`):

```bash
uv run main.py
```

Open the docs at `http://localhost:8000/docs` or `http://localhost:8000/redoc`.

## API Endpoints (high level)

- `GET /health` - Basic health check

Agent endpoints under `/api/v1` - examples:

- `POST /api/v1/agent/sessions?user_id=<uuid>` - Create chat session
- `GET /api/v1/agent/sessions?user_id=<uuid>` - List sessions
- `GET /api/v1/agent/sessions/{session_id}?user_id=<uuid>` - Get session
- `POST /api/v1/agent/sessions/{session_id}/chat?user_id=<uuid>` - Send a chat (non-streaming)
- `POST /api/v1/agent/sessions/{session_id}/chat/stream?user_id=<uuid>` - Send a chat with SSE streaming

Refer to the OpenAPI docs (`/docs`) for request/response schemas and examples.

## Available Endpoints (detailed)

All agent endpoints are mounted under `/api/v1`. The app exposes OpenAPI interactive docs at `/docs` and ReDoc at `/redoc`.

- **Health**

  - `GET /health`
  - Description: Basic service health check
  - Response: `{ "status": "healthy", "service": "repo-agent", "version": "0.4.1" }`

- **Create Session**

  - `POST /api/v1/agent/sessions?user_id=<uuid>`
  - Query params: `user_id` (UUID) — required
  - Request body (JSON): `CreateSessionRequest`
    - Example (orchestrator — default, unified multi-domain chat):
      ```json
      {
        "repo_namespace": "org/repo",
        "title": "My code chat"
      }
      ```
    - Example (per-agent — old flow, single-domain chat):
      ```json
      {
        "repo_namespace": "org/repo",
        "title": "Security review",
        "agent_type": "security"
      }
      ```
    - Valid `agent_type` values: `orchestrator` (default), `general`, `security`, `database`, `api`, `performance`, `architecture`, `testing`, `code_quality`
  - Response: `SessionResponse` (201 Created)

- **List Sessions**

  - `GET /api/v1/agent/sessions?user_id=<uuid>&status=<optional>&limit=<optional>&offset=<optional>`
  - Response: `SessionListResponse`

- **Get Session**

  - `GET /api/v1/agent/sessions/{session_id}?user_id=<uuid>`
  - Response: `SessionResponse` (404 if not found)

- **Update Session**

  - `PATCH /api/v1/agent/sessions/{session_id}?user_id=<uuid>`
  - Request body: `UpdateSessionRequest` (partial fields allowed)
  - Response: `SessionResponse`

- **Delete Session (soft-delete)**

  - `DELETE /api/v1/agent/sessions/{session_id}?user_id=<uuid>`
  - Response: 204 No Content (404 if not found)

- **Get Messages**

  - `GET /api/v1/agent/sessions/{session_id}/messages?user_id=<uuid>&limit=<optional>&offset=<optional>`
  - Response: `MessageListResponse`

- **Chat (synchronous)**

  - `POST /api/v1/agent/sessions/{session_id}/chat?user_id=<uuid>`
  - Request body: `ChatRequest`
    - Example:
      ```json
      {
        "message": "Explain how the repository's DB migrations are organized.",
        "model_id": "openai:gpt-5.1",
        "repo_namespace": "org/repo"
      }
      ```
  - Response: `ChatResponse` containing both user and assistant saved messages

- **Chat (streaming / SSE)**
  - `POST /api/v1/agent/sessions/{session_id}/chat/stream?user_id=<uuid>`
  - Request body: `ChatRequest` (same shape as synchronous chat)
  - Response: Server-Sent Events stream (`text/event-stream`) that yields `StreamChunk` shaped data. The final event contains metadata with saved message IDs.

Visit the interactive docs to inspect full request/response schemas and try calls:

```text
OpenAPI docs: http://<host>:<port>/docs
ReDoc docs:   http://<host>:<port>/redoc
```

For programmatic clients use the OpenAPI spec (available at `/openapi.json`) to generate typed SDKs.

## Agent Behavior and Integrations

- The agent fetches a system prompt and available tools from an MCP server at startup (configured via `MCP_SERVER_URL` and `MCP_PROMPT_NAME`).
- The agent uses an embeddings model (configurable) and a LangGraph Postgres store for memories and checkpointing. Use `DATABASE_URL_FOR_AGENT` to provide a separate DB if desired.
- Summarization middleware automatically summarizes conversation history to keep memory usage bounded (threshold configurable via `SUMMARIZATION_TRIGGER_THRESHOLD`).

### Orchestrator Agent

The default session type is **orchestrator** — a single agent that dynamically routes across all domains (security, database, API, performance, architecture, testing, code quality, general) within one conversation.

- **Embedding-based router** classifies each user message into a domain using cosine similarity against precomputed domain description vectors (~50ms overhead per message).
- **Dynamic prompt injection** loads the matching domain-specific prompt and injects it per-message, so the agent's expertise adapts on every turn without losing conversation history.
- **Auto-routed memory** stores and retrieves memories in per-domain namespaces based on the router's classification — no cross-domain noise.
- **Domain tracking** records which domains have been covered in `session_metadata.domains_used` and tags each message with `routed_domain` in its metadata.
- **Both flows coexist**: sessions created with `agent_type="orchestrator"` (default) use the router; sessions created with a specific type like `"security"` use the old dedicated per-agent flow with a baked-in prompt.

## Logging & Middleware

- Request logging middleware is added via `src/middlewares/request_logger_middleware.py`.
- Exceptions are handled by `src/exceptions/global_handler.py` and registered on startup.
