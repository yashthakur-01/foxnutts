from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase_client.client import supabase
from app.controllers.agent_engine import get_chatbot_agent
from langchain_core.messages import HumanMessage, AIMessage
import asyncio

load_dotenv()

class MessageRequest(BaseModel):
    workspace_id: str
    customer_id: str
    session_id: str
    message: str

router = APIRouter()
from app.helpers.cache import (
    get_cached_workspace_config,
    invalidate_workspace_cache,
    get_cached_chat_history,
    append_chat_message_to_cache,
    invalidate_observability_cache
)

class InvalidateCacheRequest(BaseModel):
    workspace_id: str

@router.post("/api/invalidate-workspace-cache")
async def handle_invalidate_cache(body: InvalidateCacheRequest):
    success = invalidate_workspace_cache(body.workspace_id)
    return JSONResponse(status_code=200, content={"success": success, "message": "Cache invalidated"})

@router.post("/api/chat")
async def return_message(body: MessageRequest):
    try:
        # 1. Fetch AI config from Redis cache (fallback to Supabase)
        workspace_data = await asyncio.to_thread(get_cached_workspace_config, body.workspace_id)

        temperature = workspace_data.get("temperature", 0.7)
        model_name = workspace_data.get("model_name", "gpt-4o")
        provider = workspace_data.get("provider", "openai")
        system_prompt = workspace_data.get("system_prompt", "You are a helpful assistant.")
        search_enabled = workspace_data.get("search_enabled", False)
        similarity_threshold = float(workspace_data.get("similarity_threshold", 0.6))
        
        # 2. Get the compiled LangGraph agent
        agent = get_chatbot_agent()
        
        # 3. Setup configuration (used by context_retriever)
        config = {
            "configurable": {
                "customerId": body.customer_id,
                "workspaceId": body.workspace_id,
                "similarityThreshold": similarity_threshold
            }
        }
        
        # 4. Fetch chat history from Redis cache (fallback to Supabase)
        cached_msgs = await asyncio.to_thread(get_cached_chat_history, body.session_id, 8)
        
        formatted_history = []
        for msg in cached_msgs:
            sender = msg.get("sender_type")
            content = msg.get("content")
            if sender == "human":
                # Skip if it matches the current incoming message to avoid duplicate
                if content == body.message:
                    continue
                formatted_history.append(HumanMessage(content=content))
            elif sender == "ai":
                formatted_history.append(AIMessage(content=content))

        # Append current incoming human query to Redis chat history cache
        await asyncio.to_thread(append_chat_message_to_cache, body.session_id, "human", body.message)

        # 5. Setup initial state
        initial_state = {
            "system_prompt": system_prompt,
            "query": [body.message],
            "messages": formatted_history,
            "model": {
                "provider": provider,
                "model_name": model_name,
                "temperature": temperature,
                "max_tokens": 512
            },
            "search_enabled": search_enabled,
            "query_context_pairs": []
        }
        
        print(f"Invoking LangGraph Agent for message: {body.message}")
        
        # 6. Stream the graph and store the final response
        async def generate_response():
            full_response = ""
            trajectory = []
            error_messages = []
            query_context_pairs = []
            query_type = "genuine_query"
            STREAMABLE_NODES = {"chatbot_node", "generic_response_node", "clarify_node", "unsatisfactory_handle_node"}
            current_streaming_node = None
            
            try:
                async for event in agent.astream_events(initial_state, config, version="v2"):
                    if event["event"] == "on_chat_model_stream":
                        node = event.get("metadata", {}).get("langgraph_node")
                        if node not in STREAMABLE_NODES:
                            continue

                        if node != current_streaming_node:
                            if current_streaming_node is not None:
                                full_response = ""
                            current_streaming_node = node

                        chunk = event["data"]["chunk"].content
                        if chunk:
                            full_response += chunk
                            yield chunk
                            
                    elif event["event"] == "on_chain_end":
                        output = event["data"].get("output")
                        if isinstance(output, dict) and "system_prompt" in output and "trajectory" in output:
                            trajectory = output["trajectory"]
                            if "error_messages" in output:
                                error_messages = output["error_messages"]
                            if "query_context_pairs" in output:
                                query_context_pairs = output["query_context_pairs"]
                            if "query_type" in output:
                                query_type = output["query_type"]
                            elif "route" in output and isinstance(output["route"], list) and len(output["route"]) > 0:
                                if output["route"][0] == "generic_or_repetitive":
                                    query_type = "generic_or_repetitive"
                            
                            # Fallback if non-LLM streaming node returned an AIMessage in final state
                            if not full_response and "messages" in output and output["messages"]:
                                last_msg = output["messages"][-1]
                                if hasattr(last_msg, "content") and last_msg.content:
                                    full_response = str(last_msg.content)
                                    yield full_response
                            
                # Calculate metrics
                total_tokens = 0
                total_duration_ms = 0
                for step in trajectory:
                    total_duration_ms += step.get("duration_ms", 0)
                    if step.get("tokens") and isinstance(step["tokens"], dict):
                        total_tokens += step["tokens"].get("total_tokens", 0)
                        
                # 7. Store the final AI response to the database & Redis cache
                def serialize_item(item):
                    if isinstance(item, dict):
                        return {k: serialize_item(v) for k, v in item.items()}
                    elif isinstance(item, (list, tuple)):
                        return [serialize_item(i) for i in item]
                    elif hasattr(item, "content"):
                        return {"type": item.__class__.__name__, "content": str(item.content)}
                    elif isinstance(item, (int, float, str, bool)) or item is None:
                        return item
                    else:
                        return str(item)

                clean_trajectory = serialize_item(trajectory)
                clean_error_messages = serialize_item(error_messages)
                clean_query_context_pairs = serialize_item(query_context_pairs)

                try:
                    # Insert AI message to Supabase
                    await asyncio.to_thread(
                        lambda: supabase.table("messages").insert({
                            "session_id": body.session_id,
                            "sender_type": "ai",
                            "content": full_response,
                            "workspace_id": body.workspace_id
                        }).execute()
                    )

                    # Append AI message to Redis chat history cache
                    await asyncio.to_thread(append_chat_message_to_cache, body.session_id, "ai", full_response)
                    
                    # Insert agent trace to Supabase
                    await asyncio.to_thread(
                        lambda: supabase.table("agent_traces").insert({
                            "session_id": body.session_id,
                            "workspace_id": body.workspace_id,
                            "query": body.message,
                            "final_response": full_response,
                            "total_tokens": total_tokens,
                            "total_duration_ms": total_duration_ms,
                            "trajectory": clean_trajectory,
                            "error_messages": clean_error_messages,
                            "query_context_pairs": clean_query_context_pairs,
                            "query_type": query_type
                        }).execute()
                    )

                    # Invalidate observability cache for fresh analytics
                    await asyncio.to_thread(invalidate_observability_cache, body.workspace_id)
                    print("[MessageRoute] AI response cached and observability cache invalidated successfully.")
                except Exception as db_e:
                    print("Error saving message or traces to database/cache:", db_e)
            
            except Exception as stream_e:
                print("Error occurred while streaming message:", stream_e)
                yield f"\n\nError: {str(stream_e)}"

        return StreamingResponse(generate_response(), media_type="text/plain")
    except Exception as e:
        print("Error occurred while processing message:", e)
        return JSONResponse(
            status_code=500,
            content={"message": f"Error occurred while processing message - {str(e)}", "success": False}
        )
