from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from server.supabase.client import supabase


load_dotenv()

class MessageRequest(BaseModel):
    workspace_id: str
    customer_id: str
    session_id: str
    message: str

router = APIRouter()

@router.post("/api/chat")
def return_message(body: MessageRequest):
    try:
        result = supabase.table("workspace").select("temperature, model_name, provider").eq("id", body.workspace_id).execute()
        if not result.data:
            raise Exception(f"Workspace with id {body.workspace_id} not found.")
        
        workspace_data = result.data[0]

        temperature = workspace_data.get("temperature", 0.7)
        model_name = workspace_data.get("model_name")
        provider = workspace_data.get("provider")
        
        print("Message received:", body.message)
        return JSONResponse(
            status_code=200,
            content={"message": "Message received", "success": True}
        )
    except Exception as e:
        print("Error occurred while processing message:", e)
        return JSONResponse(
            status_code=500,
            content={"message": f"Error occurred while processing message - {str(e)}", "success": False}
        )

