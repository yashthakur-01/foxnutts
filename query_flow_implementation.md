# End-to-End Query Handling & Database Flow

This document outlines the ideal flow for handling a user query in the RAG chatbot architecture. It ensures secure configuration, persistent chat history, and a responsive streaming experience.

## 1. User Input (React Frontend)
- The user types a message into the chat interface.
- The frontend client sends a `POST` request to the Next.js internal API route: `/api/chat/sendMessage`.
- **Payload:** `{ workspace_id, session_id, message }`

## 2. Next.js Proxy & Pre-Logging (Next.js API)
The Next.js API acts as a secure middleman so the FastAPI server isn't exposed directly to the public web.
- **Database Interaction 1 (Validate Workspace):** Next.js queries Supabase to ensure the `workspace_id` is valid and retrieves the associated `customer_id`.
- **Database Interaction 2 (Log Human Message):** Next.js inserts the user's message into the `messages` table in Supabase. 
  - *Data saved:* `session_id`, `workspace_id`, `sender_type: "human"`, `content: message`.
- Next.js then securely forwards the payload (now including `customer_id`) to the FastAPI backend (`/api/chat`), attaching an `X-API-Key` header for authorization.

## 3. Backend Setup & History Fetching (FastAPI)
FastAPI's `MessageRoute.py` receives the request.
- **Database Interaction 3 (Fetch AI Config):** FastAPI queries the `workspace` table in Supabase to get the chatbot's parameters for this specific workspace (`provider`, `model_name`, `temperature`, `system_prompt`, `search_enabled`).
- **Database Interaction 4 (Fetch Chat History):** FastAPI queries the `messages` table to get the last ~5-10 messages for this `session_id`. This gives the AI conversation context so it can answer follow-up questions.

## 4. The LangGraph Engine Execution (FastAPI)
FastAPI passes the configuration, chat history, and the new query into the LangGraph engine (`agent_engine.py`).
- **Router Node:** The LLM checks if the query is a simple greeting (returns a generic response) or requires information (proceeds to retrieval).
- **Retrieval Node:** If it requires information, the engine queries the **Vector Database (Pinecone)** to fetch relevant document chunks using the `workspace_id` as a metadata filter.
- **Chatbot Node:** The LLM drafts an answer using the retrieved context. (It can also trigger the `web_search` tool here if real-time data is needed).
- **Evaluator Node:** A "Judge LLM" reviews the drafted answer. If it's unsatisfactory, it loops back to rephrase the search query. If it's satisfactory, the graph ends.

## 5. Streaming & Post-Logging
Once the LangGraph engine starts producing the final satisfactory response, it is returned to the user.
- **Streaming Phase:** FastAPI streams the response chunks back to the Next.js proxy. Next.js immediately pipes these chunks to the browser using Web Streams (`text/event-stream`). The user sees the text appearing in real-time.
- **Database Interaction 5 (Log AI Message):** Once the stream is complete, the final AI response must be saved to the `messages` table. 
  - *Best Practice:* It is usually best to have a background task in **FastAPI** save this to Supabase (`sender_type: "ai"`) right after the stream completes. This ensures the message is saved even if the user closes their browser mid-stream.

---

## Summary of Database Responsibilities

| System | Database Action | Purpose |
| :--- | :--- | :--- |
| **Next.js** | SELECT from `workspace` | Validate the request before hitting FastAPI. |
| **Next.js** | INSERT into `messages` | Save the human's question immediately. |
| **FastAPI** | SELECT from `workspace` | Get the LLM model name, provider, and temperature. |
| **FastAPI** | SELECT from `messages` | Get the chat history for context. |
| **FastAPI** | Query Pinecone (Vector) | Retrieve relevant document chunks. |
| **FastAPI** | INSERT into `messages` | Save the AI's final answer to the chat history. |
