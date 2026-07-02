# RAG Pipeline Flow Review & Improvement Suggestions

Your current Retrieval-Augmented Generation (RAG) architecture is already quite robust. It successfully implements several advanced RAG concepts like structural parsing, semantic re-ranking, and agentic evaluation. 

Here is a quick summary of your current flow, followed by actionable ways to take your retrieval quality to the next level.

## Current Flow Analysis

1. **Ingestion (`main.py`, `0_pdf_parsing.py`, `0_markdown_parsing.py`)**
   - Documents are pulled from Cloudflare R2.
   - Text is cleaned (OCR artifacts, boilerplate headers/footers removed).
   - Document structure is analyzed (headings detected, tables/lists preserved).
   - Context enrichment is applied (document and section titles are prepended).
   - Chunks are created at `1024` tokens with `200` token overlap.

2. **Embedding & Storage (`1_embedding_pipeline.py`)**
   - Chunks are converted into dense vector embeddings using Cohere (`embed-english-v3.0`).
   - Embeddings are pushed in batches to a Pinecone vector database with tenant and workspace metadata.

3. **Retrieval (`2_query_pipeline.py`)**
   - The user's query is embedded.
   - Pinecone fetches the top 13 (`k+8`) most relevant chunks using dense vector similarity.
   - A Jina AI cross-encoder model reranks these 13 chunks to find the absolute top 5 most relevant ones.

4. **Agentic Generation & Evaluation (`agent_engine.py`)**
   - A LangGraph state machine routes the query.
   - If it's a "genuine query", it retrieves context and passes it to Groq.
   - An LLM judge evaluates the generated answer. If unsatisfactory, it can rewrite the query and try again, or ask the user for clarification.

---

## Suggestions to Improve Retrieval Quality

While your pipeline is solid, the most common bottlenecks in RAG systems occur during the **chunking** and **retrieval** phases. Here are the highest-impact improvements you can make:

### 1. Enable Hybrid Search (Dense + Sparse Retrieval)
**The Problem:** Dense embeddings (like Cohere) are great at understanding *semantics* ("vacation policy" matches "time off"), but they often fail at exact keyword matches (e.g., searching for a specific employee ID like "EMP-9281" or an obscure product name).
**The Solution:** Pinecone supports **Hybrid Search**. You can generate sparse vectors (using BM25 or SPLADE) alongside your dense Cohere embeddings. 
- You would retrieve the top results from both methods and fuse them together (using Reciprocal Rank Fusion) before sending them to the Jina reranker. 
- *Implementation:* Use Langchain's `PineconeHybridSearchRetriever`.

### 2. Implement "Small-to-Big" (Parent Document) Retrieval
**The Problem:** Chunks of 1024 tokens are quite large. Embedding a large chunk dilutes the meaning of specific sentences within it. If a user asks a highly specific question, a 1024-token chunk might not score high enough in cosine similarity to be retrieved.
**The Solution:** Chunk your documents into small, highly precise sentences or paragraphs (e.g., 128-256 tokens) for the *embedding phase*. However, when Pinecone matches a small chunk, you return the **entire parent chunk** (1024 tokens) to the LLM so it doesn't lose the surrounding context.
- *Implementation:* Langchain provides a `ParentDocumentRetriever` specifically for this.

### 3. Optimize Cohere v3 `input_type`
**The Problem:** Cohere's `v3` embedding models are specifically trained to differentiate between the text being stored and the search query being asked. 
**The Solution:** You must explicitly pass `input_type` to get the best accuracy out of Cohere v3.
- In `1_embedding_pipeline.py` (when storing documents): 
  `CohereEmbeddings(..., model="embed-english-v3.0", input_type="search_document")`
- In `2_query_pipeline.py` (when searching): 
  `CohereEmbeddings(..., model="embed-english-v3.0", input_type="search_query")`
  *(Note: You'll need to instantiate a separate Cohere client in the query pipeline just for this, or configure it dynamically).*

### 4. Front-load Query Rewriting (Hypothetical Document Embeddings - HyDE)
**The Problem:** User queries are often short, poorly worded, or lack context (e.g., "how much leave do I get?"). Vector databases struggle to match short questions to long, formal policy documents. Your current architecture waits for the LLM judge to fail before rewriting the query.
**The Solution:** Before querying Pinecone, use a fast, cheap LLM (like `llama3-8b` on Groq) to write a "fake" answer to the user's question, or expand the query. You then embed this *fake answer* and use it to search Pinecone. 
- *Implementation:* Langchain has a built-in `HypotheticalDocumentEmbedder` (HyDE).

### 5. Self-Querying (Metadata Filtering)
**The Problem:** If a user asks, "What is the vacation policy in the Employee Handbook?", vector search might return vacation policies from the *Manager Handbook* just because the semantics are similar.
**The Solution:** Use an LLM to extract metadata filters from the user's natural language query *before* hitting Pinecone.
- *Implementation:* Langchain's `SelfQueryRetriever` can translate "in the Employee Handbook" into a deterministic Pinecone filter: `{"filter": {"document_title": {"$eq": "Employee Handbook"}}}`.


### Summary of Priority
If I were to prioritize these for you:
1. **High Priority / Easy Win:** Fix the Cohere `input_type` for documents vs. queries.
2. **High Priority / Medium Effort:** Implement Hybrid Search (BM25 + Cohere) in Pinecone.
3. **Medium Priority / Medium Effort:** Parent Document Retrieval.
