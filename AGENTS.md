# AGENTS.md — Codebase Architecture & Technical Context

This document serves as the authoritative context map for AI coding agents working in this repository.

---

## 📁 Repository Structure

```text
e:\cb\
├── client\                                  # Next.js 16 Frontend Application
│   ├── src\
│   │   ├── app\
│   │   │   ├── api\customer\                # Next.js Backend API Routes
│   │   │   │   ├── createWorkspace\route.ts # Creates workspace entry in Supabase
│   │   │   │   ├── deleteFile\route.ts      # Removes DB row, R2 object, & triggers Celery delete task
│   │   │   │   ├── getFiles\route.ts        # Lists workspace files & statuses
│   │   │   │   ├── logout\route.ts          # Invalidates user auth session cache
│   │   │   │   ├── observability\
│   │   │   │   │   ├── metrics\route.ts     # Calculates RPM, TPM, RPD, TPD & timeline series
│   │   │   │   │   └── traces\route.ts      # Returns paginated traces with Redis Set tracker
│   │   │   │   ├── reprocessDocument\route.ts # Triggers Celery reprocess task
│   │   │   │   ├── updateConfig\route.ts    # Updates workspace LLM settings & purges workspace cache
│   │   │   │   └── uploadFile\route.ts      # Generates R2 presigned upload URL
│   │   │   ├── chat\page.tsx                # RAG Chat & File Management Dashboard
│   │   │   └── observability\page.tsx       # Observability Analytics Dashboard
│   │   ├── components\
│   │   │   └── ObservabilitySection.tsx     # KPI Rate Cards, SVG Charts, & Trace Inspection Table
│   │   ├── lib\
│   │   │   ├── authCache.ts                 # 60s In-Memory Auth Session Cache
│   │   │   └── redisClient.ts               # Next.js ioredis Singleton Instance
│   │   └── supabase\
│   │       ├── adminClient.ts               # Supabase Service Role Admin Client
│   │       └── schema.sql                   # Database SQL DDL & Row Level Security Policies
│   └── package.json
│
└── rag-backend\server\                      # Python FastAPI & LangGraph RAG Service
    └── app\
        ├── main.py                          # FastAPI Application Entry & CORS Setup
        ├── celery_app.py                    # Celery Worker Configuration & Redis Broker Init
        ├── tasks.py                         # Celery Tasks (process_document, reprocess_document, delete_document)
        ├── controllers\
        │   ├── 0_pdf_parsing.py             # PyMuPDF / PDF Plumber extraction logic
        │   ├── 1_embedding_pipeline.py      # Chunking with page headers, Cohere embeddings, Pinecone upsert
        │   ├── 2_query_pipeline.py          # Vector similarity search & metadata filtering
        │   └── agent_engine.py              # LangGraph Workflow Definition & Node Trajectories
        ├── helpers\
        │   └── cache.py                     # Redis Cache Helpers & Set Tracker Invalidation
        └── routes\
            ├── FileProcessRoute.py          # /api/process-document, /api/reprocess-document, /api/delete-document
            └── MessageRoute.py              # /api/chat (Streaming SSE response & trace recording)
```

---

## 🔄 Execution Trajectories & Data Flows

### 1. RAG Chat Query Trajectory (`/api/chat`)
```text
Client Request ──> Next.js (/api/chat/sendMessage) ──> Supabase DB (Inserts Human Message)
                                 │
                                 ▼
                    FastAPI (/api/chat in MessageRoute.py)
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
[1. Fetch Redis History]                        [2. Append Human Msg to Redis]
 `chat_history:{session_id}`                     `chat_history:{session_id}`
         │
         ▼
[3. Run LangGraph Engine (agent_engine.py)]
  ├── Step A: genuine_generic_router
  │     ├── If casual/greeting ──> generic_response_node ──> Return LLM Answer
  │     └── If domain/policy   ──> genuine_query
  │
  ├── Step B: context_retriever
  │     └── Dense/Sparse Hybrid Query in Pinecone ──> Extract matching text chunks
  │
  └── Step C: chatbot_node
        └── Grounded Prompt Generation ──> LLM Completion Stream
         │
         ▼
[4. Post-Stream Operations]
  ├── Append AI Message to Redis (`chat_history:{session_id}`)
  ├── Insert Execution Trace to Supabase `agent_traces` table
  └── ⚡ Invalidate Observability Cache (`invalidate_observability_cache(workspace_id)`)
        └── Clears `observability_metrics:{workspace_id}` & Set tracker `workspace_trace_keys:{workspace_id}`
```

### 2. Document Processing & Ingestion Trajectory
```text
1. React Frontend sends file ──> Next.js (/api/customer/uploadFile) ──> Returns Presigned R2 URL
2. XHR Uploads file (0%-100% loader) directly to Cloudflare R2 Bucket
3. Upon 100% completion ──> Next.js creates record in Supabase `files` table (status: 'uploaded')
4. Next.js calls FastAPI (/api/process-document)
5. FastAPI enqueues `process_document_task.delay(...)` to Celery Broker (< 10ms HTTP 200 response)
6. Celery Worker picks up task:
   - Updates Supabase status to 'processing'
   - Downloads PDF from R2
   - Extracts text and formats chunks with headers: "[Page X] [File: doc.pdf] [Section: title]\n<content>"
   - Generates Cohere embeddings & upserts vectors to Pinecone
   - Updates Supabase status to 'completed'
```

---

## 🔑 Redis Cache Key Specification

| Cache Key Pattern | TTL | Data Type | Purpose |
| :--- | :--- | :--- | :--- |
| `workspace_config:{workspace_id}` | 300s (5m) | String (JSON) | Caches system prompt, temperature, provider, model name, and similarity threshold. |
| `chat_history:{session_id}` | 3600s (1h) | List (JSON) | Caches last 20 alternating human/AI messages for instant history retrieval. |
| `observability_metrics:{workspace_id}` | 600s (10m) | String (JSON) | Caches summary KPIs, RPM/TPM/RPD/TPD rate metrics, and time-series timelines. |
| `observability_traces:{workspace_id}:{page}:{limit}` | 600s (10m) | String (JSON) | Caches paginated execution trace records. |
| `workspace_trace_keys:{workspace_id}` | 600s (10m) | **Set** (Strings) | **Tracker Set**: Stores all active `observability_traces:...` key names for $O(1)$ instant invalidation. |

---

## ⚙️ Environment Variables Contract

```ini
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-supabase-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Cloudflare R2 / AWS S3
R2_BUCKET_NAME=your-bucket-name
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key

# Vector DB & LLM Providers
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX=your-index-name
COHERE_API_KEY=your-cohere-api-key
GROQ_API_KEY=your-groq-api-key
OPENAI_API_KEY=your-openai-api-key

# Cache & Backend Secrets
REDIS_URL=redis://localhost:6379/0
FASTAPI_URL=http://127.0.0.1:8000
FASTAPI_SECRET_KEY=your-secret-api-key
```
