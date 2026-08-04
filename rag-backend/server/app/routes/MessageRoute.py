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

@router.post("/api/chat")
async def return_message(body: MessageRequest):
    try:
        # 1. Fetch AI config from Supabase
        result = await asyncio.to_thread(
            lambda: supabase.table("workspace").select("temperature, model_name, provider, system_prompt, search_enabled").eq("id", body.workspace_id).execute()
        )
        if not result.data:
            raise Exception(f"Workspace with id {body.workspace_id} not found.")
        
        workspace_data = result.data[0]

        temperature = workspace_data.get("temperature", 0.7)
        model_name = workspace_data.get("model_name", "gpt-4o")
        provider = workspace_data.get("provider", "openai")
        system_prompt = workspace_data.get("system_prompt", "You are a helpful assistant.")
        search_enabled = workspace_data.get("search_enabled", False)
        
        # 2. Get the compiled LangGraph agent
        agent = get_chatbot_agent()
        
        # 3. Setup configuration (used by context_retriever)
        config = {
            "configurable": {
                "customerId": body.customer_id,
                "workspaceId": body.workspace_id
            }
        }
        
        # 4. Fetch chat history (last 8 messages)
        history_result = await asyncio.to_thread(
            lambda: supabase.table("messages").select("sender_type, content").eq("session_id", body.session_id).order("created_at", desc=True).limit(8).execute()
        )
        
        formatted_history = []
        if history_result.data:
            messages_data = list(reversed(history_result.data))
            
            # The current message was already inserted by Next.js prior to this call, 
            # so we pop it from history to avoid passing it twice to the LLM.
            if messages_data and messages_data[-1].get("sender_type") == "human" and messages_data[-1].get("content") == body.message:
                messages_data.pop()
                
            for msg in messages_data:
                if msg.get("sender_type") == "human":
                    formatted_history.append(HumanMessage(content=msg.get("content")))
                elif msg.get("sender_type") == "ai":
                    formatted_history.append(AIMessage(content=msg.get("content")))

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
            "search_enabled": search_enabled
        }
        
        print(f"Invoking LangGraph Agent for message: {body.message}")
        
        # 6. Stream the graph and store the final response
        async def generate_response():
            full_response = ""
            trajectory = []
            error_messages = []
            # Only stream tokens from nodes that produce user-facing answers.
            # All other nodes (router, evaluator, rephraser) are internal and must be silent.
            STREAMABLE_NODES = {"chatbot_node", "generic_response_node", "clarify_node"}
            current_streaming_node = None
            
            try:
                async for event in agent.astream_events(initial_state, config, version="v2"):
                    if event["event"] == "on_chat_model_stream":
                        node = event.get("metadata", {}).get("langgraph_node")
                        if node not in STREAMABLE_NODES:
                            continue  # Skip router/evaluator/rephraser tokens

                        # If a different answer-node starts streaming, reset for fresh answer
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
                        # The final graph state contains all state keys like 'system_prompt'
                        # We use this to identify the complete final state rather than intermediate node updates.
                        if isinstance(output, dict) and "system_prompt" in output and "trajectory" in output:
                            trajectory = output["trajectory"]
                            if "error_messages" in output:
                                error_messages = output["error_messages"]
                            
                # Calculate metrics
                total_tokens = 0
                total_duration_ms = 0
                for step in trajectory:
                    total_duration_ms += step.get("duration_ms", 0)
                    if step.get("tokens") and isinstance(step["tokens"], dict):
                        total_tokens += step["tokens"].get("total_tokens", 0)
                        
                # 7. Store the final AI response to the database
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

                try:
                    # Insert message
                    await asyncio.to_thread(
                        lambda: supabase.table("messages").insert({
                            "session_id": body.session_id,
                            "sender_type": "ai",
                            "content": full_response,
                            "workspace_id": body.workspace_id
                        }).execute()
                    )
                    
                    # Insert agent trace
                    await asyncio.to_thread(
                        lambda: supabase.table("agent_traces").insert({
                            "session_id": body.session_id,
                            "workspace_id": body.workspace_id,
                            "query": body.message,
                            "final_response": full_response,
                            "total_tokens": total_tokens,
                            "total_duration_ms": total_duration_ms,
                            "trajectory": clean_trajectory,
                            "error_messages": clean_error_messages
                        }).execute()
                    )
                    print("Agent responded and traces saved successfully.")
                except Exception as db_e:
                    print("Error saving message or traces to database:", db_e)
            
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
