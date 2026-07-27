<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Project Context: RAG Chatbot Application

### Overview
This project is a multi-tenant Retrieval-Augmented Generation (RAG) chatbot system. Customers can create and configure distinct "workspaces" (chatbots), upload documents to be indexed, and interact with an AI agent that retrieves and synthesizes information from those documents.

### Tech Stack
- **Frontend**: Next.js 16 (App Router), React 19, Tailwind CSS v4, TypeScript.
- **Backend**: FastAPI (Python), LangChain, LangGraph, Pinecone, Cohere.
- **Database & Auth**: Supabase (PostgreSQL), `@supabase/ssr`.
- **Document Parsing**: Docling, PyMuPDF, MarkItDown.
- **Storage**: AWS S3/Multer for file handling.

### Backend Architecture (`rag-backend/server`)
The backend is a FastAPI application orchestrating the entire RAG pipeline.
1. **Document Processing (`/api/process-document`)**: 
   - Files are parsed using specific pipelines (`0_markdown_parsing.py`, `0_pdf_parsing.py`).
   - Text is chunked and embedded using the embedding pipeline (`1_embedding_pipeline.py`) into Pinecone.
2. **Chatbot Agent Engine (`agent_engine.py`)**: 
   - Implemented as a highly complex **LangGraph** state machine.
   - **Nodes included**: 
     - `genuine_generic_router`: Classifies if the query needs retrieval or is generic/repetitive.
     - `context_retriever`: Fetches relevant context from Pinecone vector DB (`2_query_pipeline.py`).
     - `chatbot_node`: The main LLM node (supports Gemini, OpenAI, Groq) generating a grounded response.
     - `evaluator_node`: A judge LLM that evaluates the response's quality. Routes to `satisfactory`, `unsatisfactory`, `query_rephrase`, `revise`, or `clarify`.
     - `query_rephraser_node`: Re-writes the user's query if the evaluation fails, looping back to retrieval.
     - `tools`: Includes a Tavily web search tool for real-time information.

### Frontend Architecture (`client/src`)
The client manages the UI, customer configurations, and acts as an intermediate proxy for the backend.
1. **Supabase Integration**: Next.js handles user authentication and fetches/updates workspace settings (chatbot name, system prompt, temperature, chunk size, top_k, etc.) from the Supabase `workspace` table.
2. **API Routes (`app/api/customer/*`)**: 
   - Operations for `createWorkspace`, `updateConfig`, `uploadFile`, `processFile`, `deleteFile`.
3. **Chat Proxy (`app/api/chat/sendMessage/route.ts`)**: 
   - Securely receives chat requests.
   - Saves the user's query into the Supabase `messages` table.
   - Forwards the request to the FastAPI backend (`/api/chat`).
   - Streams the AI's response directly back to the browser utilizing Web Streams and Server-Sent Events (SSE) or chunked transfer.

### Agent Workflow Guidelines
- **Configuration Flow**: Any changes to chatbot settings must update the Supabase `workspace` table, as the FastAPI backend fetches runtime configurations directly from there for every request.
- **FastAPI/Next.js Contract**: The Next.js API acts as a secure boundary. Avoid exposing the FastAPI instance directly to the browser.
- **LLM Independence**: The backend dynamically binds models (Gemini, OpenAI, Groq) based on workspace configuration. Avoid hardcoding model specific dependencies.
