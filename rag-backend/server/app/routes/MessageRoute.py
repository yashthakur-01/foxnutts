from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from server.supabase.client import supabase
from server.app.controllers.agent_engine import get_chatbot_agent
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
        
        # 6. Invoke the graph
        final_state = await agent.ainvoke(initial_state, config)
        
        # 7. Extract the AI's final response
        ai_response_text = final_state["messages"][-1].content
        
        print("Agent responded successfully.")
        
        return JSONResponse(
            status_code=200,
            content={"message": ai_response_text, "success": True}
        )
    except Exception as e:
        print("Error occurred while processing message:", e)
        return JSONResponse(
            status_code=500,
            content={"message": f"Error occurred while processing message - {str(e)}", "success": False}
        )
