from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import importlib
from server.supabase.client import supabase

class ProcessDocument(BaseModel):
    workspace_id: str
    customer_id: str
    fileName: str    

router = APIRouter()

@router.post("/api/process-document")
async def process_document(
    body: ProcessDocument
) -> None:
    try: 

        response = await supabase.table("workspace").select("chunk_size, chunk_overlap").eq("id", body.workspace_id).execute()
        
        if not response.data:
            raise Exception(f"Workspace with id {body.workspace_id} not found.")
            
        workspace_data = response.data[0]
        chunk_size = workspace_data.get("chunk_size", 1024)
        chunk_overlap = workspace_data.get("chunk_overlap", 250)

        embedding_pipeline = importlib.import_module("1_embedding_pipeline")
        generate_embeddings_for_file = embedding_pipeline.generate_embeddings_for_file
        await generate_embeddings_for_file(body.fileName, chunk_size=chunk_size, chunk_overlap=chunk_overlap, customerId=body.customer_id, workspaceId=body.workspace_id)
        return JSONResponse(
            status_code=200,
            content={"message": "Document processed successfully", "success": True}
        )
    except Exception as e:
        print(f"Error occurred while processing document {body.fileName}: {e}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Error occurred while processing document - {str(e)}", "success": False}
        )