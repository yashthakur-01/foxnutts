# Enterprise Agentic RAG & AI Observability Platform

A state-of-the-art **Retrieval-Augmented Generation (RAG)** platform featuring an intelligent **LangGraph Agent Engine**, **Celery + Redis Background Processing**, **Pinecone Hybrid Vector Search**, **Multi-Layer Caching ($O(1)$ Redis Set Tracker)**, and a **Real-Time Observability Suite** with rate metrics (RPM, TPM, RPD, TPD) and time-series analytics.

---

## 🚀 Architecture Overview

```
                                      [ REACT / NEXT.JS FRONTEND ]
                                                    │
             ┌──────────────────────────────────────┼──────────────────────────────────────┐
             ▼                                      ▼                                      ▼
  1. Direct Document Upload               2. Auth Session Cache                  3. Observability Dashboard
     • XHR 0%-100% Progress Bar to R2        • In-Memory 60s TTL                    • Rate Cards: RPM, TPM, RPD, TPD
     • Asynchronous Celery Processing        • Eliminates Auth DB Latency           • 60m & 30d Time-Series SVG Graphs
             │                                      │                                   • Smart Badge: 💬 Conversational
             ▼                                      │                                      │
  [ Cloudflare R2 Storage ]                         │                                      ▼
             │                                      │                           [ Redis Set Tracker ]
             │                                      │                             Key: workspace_trace_keys:{id}
             ▼                                      ▼                             $O(1)$ Instant Invalidation
  [ FastAPI Backend ] ────────────── (Reads Redis Cache: 1ms) ──────────────────────────┤
             │                                                                             │
             ▼ (Dispatches Async Task < 10ms)                                              │
  [ Redis Broker ]                                                                         │
             │                                                                             │
             ▼ (Pulls Job)                                                                 │
  [ Celery Background Worker ] ────────────────────────────────────────────────────────────┘
    • Ingestion Pipeline: Downloads PDF, chunks with page headers "[Page X] [File: report.pdf]", embeds with Cohere
    • Reprocess Pipeline: Purges vectors from Pinecone via metadata filter before re-embedding
    • Delete Pipeline: Asynchronously deletes vectors from Pinecone index
```

---

## ✨ Key Features & Modern Engineering Practices

### 1. LangGraph Adaptive RAG Engine
* **`genuine_generic_router` Node**: Uses few-shot classification rules to route questions. Categorizes broad domain, policy, or salary queries into `genuine_query` (document search) while keeping casual chit-chat in `generic_or_repetitive`.
* **`context_retriever` Node**: Queries Pinecone hybrid index with dense (Cohere `embed-english-v3.0`) + sparse (BM25) vector retrieval.
* **`chatbot_node`**: Enforces strict context grounding (*"Answer relying ONLY on RETRIEVED CONTEXT"*) and anti-hallucination fallback (*"I cannot find this information in the provided context."*).

### 2. Celery + Redis Asynchronous Task Queue
* Heavy PDF parsing, chunking, Cohere embedding generation, and Pinecone vector upserts execute inside isolated **Celery worker threads**.
* API endpoints return HTTP `200` in **< 10ms** with `task_id` and status `queued`.
* Workers automatically update Supabase `files` table status (`uploaded` $\rightarrow$ `processing` $\rightarrow$ `completed` / `failed`).

### 3. Direct Storage Upload & Progress Loader
* Files upload directly to **Cloudflare R2** via presigned URLs using `XMLHttpRequest.upload.onprogress` to display a live `0%`–`100%` progress bar.
* Database file records are created only **after** successful transmission to R2 storage.

### 4. Page-Aware Document Chunking
* Each chunk string is prepended with explicit metadata headers: `[Page 17] [File: report.pdf] [Section: Executive Summary]`.
* Enables exact semantic and keyword matching for page-specific user queries (e.g. *"Summarize page 17"*).

### 5. Multi-Layer Caching & $O(1)$ Redis Set Tracker Pattern
* **Auth Session Cache (`authCache.ts`)**: In-memory 60-second TTL cache for user JWT session verification in Next.js.
* **Workspace Config Cache (`cache.py`)**: 5-minute Redis cache (`workspace_config:{workspace_id}`) for model settings, system prompts, and similarity thresholds.
* **Chat History Cache (`cache.py`)**: 1-hour Redis list (`chat_history:{session_id}`) holding alternating user and AI messages.
* **$O(1)$ Redis Set Tracker**:
  - Registers cached trace page keys inside a tracking Set `workspace_trace_keys:{workspace_id}`.
  - Purges cached pages in **< 0.1ms** on write without running slow $O(N)$ `redis.keys()` wildcard scans.

### 6. Real-Time Observability & Rate Analytics
* **Rate Metric Cards**: Displays real-time **RPM** (requests/min), **TPM** (tokens/min), **RPD** (requests/day), and **TPD** (tokens/day).
* **Time-Series Timelines**: Pre-filled `minute_timeline` (last 60m) and `daily_timeline` (last 30d) datasets rendered via zero-dependency SVG area/line charts.
* **Trace & Context Inspector**: Inspects full LangGraph node trajectory steps, latency per node, prompt/completion tokens, and retrieved vector text pairs.
* **Categorized Trace Badges**: Distinguishes between `💬 Conversational` chit-chat vs `✅ Context Matched` vs `⚠️ Low Relevance`.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Next.js 16 (App Router), React 19, TailwindCSS, TypeScript |
| **Backend API** | Python 3.11+, FastAPI, Uvicorn |
| **Agent Orchestration** | LangGraph, LangChain, Cohere Embeddings |
| **Task Queue** | Celery, Redis Broker |
| **Databases** | Supabase (PostgreSQL with RLS), Pinecone (Vector DB), Redis |
| **Cloud Storage** | Cloudflare R2 (S3 API Compatible) |

---

## 📊 Database Schema Summary (Supabase Postgres)

* **`users`**: Customer profiles (`id`, `email`, `name`, `created_at`).
* **`workspace`**: Bot configurations (`id`, `cust_id`, `temperature`, `model_name`, `provider`, `system_prompt`, `similarity_threshold`, `chunk_size`, `chunk_overlap`).
* **`messages`**: Session chat history (`id`, `session_id`, `workspace_id`, `sender_type`, `content`, `rating`).
* **`files`**: Uploaded file metadata & status (`id`, `file_id`, `file_name`, `file_path`, `status`).
* **`agent_traces`**: Observability execution logs (`id`, `session_id`, `workspace_id`, `query`, `final_response`, `total_tokens`, `total_duration_ms`, `trajectory`, `query_context_pairs`, `query_type`).

---

## ⚡ How to Run the Development Environment

### 1. Start Redis Server
```bash
sudo service redis-server start
```

### 2. Start Celery Worker
```powershell
cd e:\cb\rag-backend\server
celery -A app.celery_app worker --loglevel=info -P solo
```

### 3. Start Python FastAPI Server
```powershell
cd e:\cb\rag-backend\server
uvicorn app.main:app --reload --port 8000
```

### 4. Start Next.js Frontend
```powershell
cd e:\cb\client
npm run dev
```

Open **`http://localhost:3000/chat`** in your browser.
