# PLAN — rag-backend

A multi-tenant retrieval-augmented generation (RAG) API. Each tenant uploads documents, which are split into chunks and embedded into Postgres with pgvector. Questions retrieve the tenant's most relevant chunks and stream an answer over Server-Sent Events (SSE). Every query records its token use and estimated cost, and each tenant has a monthly query limit.

**Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic, Pydantic v2 with pydantic-settings, pgvector, pytest with pytest-asyncio and httpx, ruff, and uv for dependencies.

## Modules

| Module | Responsibility |
|---|---|
| tenants | Admin CRUD (`ADMIN_API_KEY`) and key rotation. Each tenant gets an API key shown once and stored as a SHA-256 hash. `GET /tenant` shows the caller's own tenant. |
| documents | Upload (txt/markdown, up to `MAX_UPLOAD_BYTES`), list, get and delete. An upload is stored, chunked and embedded in the same request. |
| chunks | Chunking logic (paragraph-aware, with overlap), plus listing a document's chunks and getting one chunk. |
| queries | `POST /queries`: embed the question, run a vector search limited to the tenant, then stream the answer over SSE (`sources`, `token`, `done`, `error` events). Also list and get past queries. |
| usage | This month's queries, tokens and estimated cost, against the tenant's limit. Admins can read any tenant's usage. |

**Layout:** each module has `routes.py → controller.py → service.py → repository.py`, plus `schemas.py` (Pydantic) and `models.py` (SQLAlchemy).

**Shared code (`app/core`):** config (pydantic-settings, validated at startup), logging, error classes and handlers (one error envelope), the database engine singleton with `Database.transaction()`, the base repository, pagination, and API-key helpers.

**Providers (`app/providers`), each chosen by a factory from config:**

| Provider | Implementations |
|---|---|
| `StorageProvider` | Local disk (default) or S3 |
| `EmbeddingProvider` | Fake (default), Bedrock Titan Text Embeddings v2 |
| `LLMProvider` | Fake (default), Anthropic, Bedrock |

- **Fake embeddings** use deterministic feature hashing (1024 dimensions), so retrieval in tests reflects real word overlap rather than random noise.
- **The fake LLM** answers deterministically from the retrieved sources, with citations.
- **The Anthropic provider** uses the official SDK's async streaming helper with `claude-opus-5-5`, explicit effort, and server-side refusal fallbacks (`fallbacks: "default"`).
- **The Bedrock provider** uses the same SDK's Bedrock Mantle client, with the client-side refusal-fallback middleware, since server-side fallbacks aren't available on Bedrock.

## Data model

```
tenants    id, name, api_key_hash (unique), monthly_query_limit, created_at
documents  id, tenant_id → tenants, filename, content_type, size_bytes, storage_key, status,
           chunk_count, error?, created_at
chunks     id, document_id → documents, tenant_id → tenants, ordinal, text, embedding vector(1024)
           HNSW index (vector_cosine_ops), index on tenant_id
queries    id, tenant_id → tenants, question, answer, top_k, source_chunk_ids, provider, model,
           input_tokens, output_tokens, estimated_cost_usd, latency_ms, status, created_at
           index on (tenant_id, created_at)
```

There's no usage table: usage is aggregated from `queries`.

## Key mechanisms

- **Tenant isolation:** `chunks.tenant_id` is stored on every row, and the vector search always filters on it. A test gives two tenants overlapping documents and checks that each only ever gets its own sources.
- **Query limit:** this month's query count is checked before any work starts. Over the limit returns 429 `QUERY_LIMIT_REACHED`.
- **Cost:** `input_tokens × LLM_INPUT_USD_PER_MTOK + output_tokens × LLM_OUTPUT_USD_PER_MTOK`. The prices are configuration and default to 0, so the code contains no invented prices.
- **Streaming:** the question is embedded and sources found before the stream starts, so errors there still return normal JSON error responses. The query row is saved when the stream ends, with status completed, refused, failed or cancelled.
- **No sources:** if nothing is retrieved, the API answers that it found nothing, without calling the LLM.

## Evaluation (script only, no numbers)

- `eval/corpus/*.md` holds a small invented corpus.
- `eval/questions.jsonl` holds questions, each with its expected source document and answer keywords.
- `scripts/eval.py` runs them against a live API and prints retrieval hit@k and keyword recall.

The README's Results section will say only "Not yet measured, run …".

## Tests

- **Unit:** chunker, fake embeddings, the fake LLM, query cost and prompt building, services with mocked repositories and providers, config validation, `start_with_secrets` with a mocked boto3 client.
- **Integration** (Postgres with pgvector): tenants and auth, upload, chunk and list, retrieval quality on a tiny corpus, tenant isolation, SSE event sequence and query persistence, query limit, usage totals.

## Deployment files

The same set as the Node repos, in Python: `Dockerfile` (multi-stage with uv, non-root, healthcheck), `scripts/start_with_secrets.py`, `deploy/ecs-task-definition.json`, and the deploy and CI workflows.

Postgres host port: **5443** (image `pgvector/pgvector:pg16`).
