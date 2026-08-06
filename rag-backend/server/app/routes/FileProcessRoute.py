from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from supabase_client.client import supabase
import asyncio

from app.tasks import process_document_task, reprocess_document_task

from app.helpers.cache import get_cached_workspace_config

class ProcessDocument(BaseModel):
    workspace_id: str
    customer_id: str
    fileName: str    

router = APIRouter()

@router.post("/api/process-document")
async def process_document(
    body: ProcessDocument
):
    try: 
        workspace_data = await asyncio.to_thread(get_cached_workspace_config, body.workspace_id)
        chunk_size = workspace_data.get("chunk_size", 1024)
        chunk_overlap = workspace_data.get("chunk_overlap", 250)

        # Dispatch task to Celery & Redis task queue
        task = process_document_task.delay(
            file_name=body.fileName,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            customer_id=body.customer_id,
            workspace_id=body.workspace_id
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Document background processing started",
                "task_id": task.id,
                "status": "queued",
                "success": True
            }
        )
    except Exception as e:
        print(f"Error occurred while queueing document processing for {body.fileName}: {e}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Error occurred while queueing document - {str(e)}", "success": False}
        )


@router.post("/api/reprocess-document")
async def reprocess_document(
    body: ProcessDocument
):
    """Delete old embeddings from Pinecone and re-embed the document."""
    try:
        workspace_data = await asyncio.to_thread(get_cached_workspace_config, body.workspace_id)
        chunk_size = workspace_data.get("chunk_size", 1024)
        chunk_overlap = workspace_data.get("chunk_overlap", 250)

        # Dispatch reprocess task to Celery (deletes old vectors + re-embeds)
        task = reprocess_document_task.delay(
            file_name=body.fileName,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            customer_id=body.customer_id,
            workspace_id=body.workspace_id
        )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Document reprocessing started (deleting old vectors + re-embedding)",
                "task_id": task.id,
                "status": "queued",
                "success": True
            }
        )
    except Exception as e:
        print(f"Error occurred while queueing document reprocessing for {body.fileName}: {e}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Error occurred while queueing reprocess - {str(e)}", "success": False}
        )