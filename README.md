# Knowledge Base MCP Server

Production MCP server for website/document extraction and vector-backed knowledge search using docling + PostgreSQL.

## Runtime Contract

- MCP route: `/mcp`
- Tool names:
  - `load_documents_tool`
  - `search_knowledge_base`
- Container port: `8000`
- Required runtime env:
  - `OPENAI_API_KEY`
- Parity/legacy env preserved:
  - `DATABASE_URL`
  - `BUSINESS_ID`

`DATABASE_URL` and `BUSINESS_ID` are still used by local scripts and parity restores, but the app path passes `database_url` and `business_id` to the MCP tool at call time.

## Features

- Smart website crawling with internal-link discovery
- HTML, PDF, DOCX, and docling-supported document extraction
- Semantic table extraction
- 512-token chunking for retrieval
- PostgreSQL + pgvector storage
- MCP HTTP server via FastMCP/uvicorn

## Local Development

```bash
pip install -r requirements.txt
cp .env.runtime.example .env
python test_extraction_chunking.py
python test_10_websites.py
```

Run the server locally:

```bash
python server.py
```

## Portable Deployment

This repo is intended to be portable across servers using:

1. a repo checkout
2. one deploy env file
3. one runtime env file
4. `docker compose up -d`

Canonical deploy files:

- `compose.yaml`
- `.env.example`
- `.env.runtime.example`
- `scripts/deploy.sh`

Create `.env.deploy` from `.env.example` for deploy-time settings:

```bash
MCP_IMAGE=knowledge-base-mcp:local
MCP_BUILD_LOCAL=1
MCP_RUNTIME_ENV_FILE=.env.runtime
```

Create `.env.runtime` from `.env.runtime.example` for container runtime settings:

```bash
OPENAI_API_KEY=...
DATABASE_URL=...
BUSINESS_ID=...
```

Deploy:

```bash
./scripts/deploy.sh .env.deploy
```

Canary deploy on loopback:

```bash
COMPOSE_PROJECT_NAME=knowledge-base-mcp-canary \
MCP_CONTAINER_NAME=knowledge-base-mcp-canary \
MCP_BIND_HOST=127.0.0.1 \
MCP_PUBLISHED_PORT=8001 \
./scripts/deploy.sh .env.deploy
```

If you want to deploy from a registry image instead of building locally, set:

```bash
MCP_IMAGE=ghcr.io/mesieou/knowledge-base-for-agents-mcp:sha-REPLACE_ME
MCP_BUILD_LOCAL=0
```

## Image Publishing

The GitHub Actions workflow publishes GHCR images, but the portable baseline does not depend on registry access. Fresh servers can deploy directly from a repo checkout with `MCP_BUILD_LOCAL=1`.

Published tags:

- `ghcr.io/<owner>/knowledge-base-for-agents-mcp:sha-<full-git-sha>`
- `ghcr.io/<owner>/knowledge-base-for-agents-mcp:latest` on the default branch

## Moving to Another Server

To move this service to a new server:

1. Install Docker + Docker Compose plugin
2. Clone this repo
3. Copy `.env.deploy`
4. Copy `.env.runtime`
5. Set `MCP_IMAGE` and `MCP_BUILD_LOCAL=1`
6. Run `./scripts/deploy.sh .env.deploy`
7. Point the app's `MCP_SERVER_URL` at the new host

No local persistent data volume is required for the current production runtime.

## Tests

```bash
python test_extraction_chunking.py
python test_10_websites.py
python test_load_documents.py
```
