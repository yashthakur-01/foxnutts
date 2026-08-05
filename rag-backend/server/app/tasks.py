import asyncio
import importlib
from app.celery_app import celery_app
from supabase_client.client import supabase
from datetime import datetime, timezone

def _update_file_status(file_name: str, status: str):
    """Helper to update file status and updated_at in Supabase."""
    try:
        supabase.table("files") \
            .update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}) \
            .eq("file_id", file_name) \
            .execute()
        print(f"[Celery Worker] Supabase status updated to '{status}' for file: {file_name}")
    except Exception as db_err:
        print(f"[Celery Worker] Warning: Failed to update Supabase status: {db_err}")

@celery_app.task(bind=True, max_retries=3)
def process_document_task(self, file_name: str, chunk_size: int, chunk_overlap: int, customer_id: str, workspace_id: str):
    """
    Celery background task for downloading, parsing, chunking, and embedding document files.
    """
    print(f"[Celery Worker] Starting embedding task for file: {file_name} (Workspace: {workspace_id})")
    
    try:
        # Dynamically import embedding pipeline
        embedding_pipeline = importlib.import_module("app.controllers.1_embedding_pipeline")
        generate_embeddings_for_file = embedding_pipeline.generate_embeddings_for_file

        # Run async embedding function inside synchronous Celery worker thread
        asyncio.run(
            generate_embeddings_for_file(
                file_name=file_name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                customerId=customer_id,
                workspaceId=workspace_id
            )
        )

        print(f"[Celery Worker] Successfully embedded file: {file_name}")
        _update_file_status(file_name, "completed")

        return {
            "status": "completed",
            "file_name": file_name,
            "workspace_id": workspace_id
        }

    except Exception as exc:
        print(f"[Celery Worker] Error processing document {file_name}: {exc}")
        _update_file_status(file_name, "failed")

        # Retry task if configured
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(bind=True, max_retries=3)
def reprocess_document_task(self, file_name: str, chunk_size: int, chunk_overlap: int, customer_id: str, workspace_id: str):
    """
    Celery background task that deletes existing Pinecone vectors for a file 
    and then re-embeds the document from scratch.
    """
    print(f"[Celery Worker] Starting REPROCESS task for file: {file_name}")
    
    try:
        embedding_pipeline = importlib.import_module("app.controllers.1_embedding_pipeline")
        delete_vectors_for_file = embedding_pipeline.delete_vectors_for_file
        generate_embeddings_for_file = embedding_pipeline.generate_embeddings_for_file

        # Step 1: Delete old embeddings from Pinecone
        print(f"[Celery Worker] Deleting old vectors for file: {file_name}")
        deleted = asyncio.run(delete_vectors_for_file(file_name))
        if not deleted:
            print(f"[Celery Worker] Warning: Vector deletion may have failed for {file_name}, continuing with re-embedding...")

        # Step 2: Re-generate embeddings from R2 file
        print(f"[Celery Worker] Re-embedding file: {file_name}")
        asyncio.run(
            generate_embeddings_for_file(
                file_name=file_name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                customerId=customer_id,
                workspaceId=workspace_id
            )
        )

        print(f"[Celery Worker] Successfully reprocessed file: {file_name}")
        _update_file_status(file_name, "completed")

        return {
            "status": "completed",
            "file_name": file_name,
            "workspace_id": workspace_id,
            "action": "reprocessed"
        }

    except Exception as exc:
        print(f"[Celery Worker] Error reprocessing document {file_name}: {exc}")
        _update_file_status(file_name, "failed")

        raise self.retry(exc=exc, countdown=10)
