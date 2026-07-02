from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from langchain_cohere import CohereEmbeddings
from langchain_core.documents import Document
import boto3
# pyrefly: ignore [missing-import]
from langchain_pinecone import PineconeVectorStore
import time
import os
from main import main

load_dotenv()

def get_embedding_model():
    cohere_api = os.environ.get("COHERE_API_KEY")
    cohere_model = os.environ.get("COHERE_MODEL")
    if(not cohere_api or not cohere_model):
        raise ValueError("Cohere API key or Cohere model name not found in environment variables.")
    return CohereEmbeddings(cohere_api_key=cohere_api, model=cohere_model)

def get_vector_store():
    pinecone_api = os.environ.get("PINECONE_API_KEY")
    index = os.environ.get("PINECONE_INDEX")
    if(not pinecone_api or not index):
        raise ValueError("Pinecone API key or index not found in environment variables.")
    try: 
        embedding = get_embedding_model() 
    except Exception as e:
        raise ValueError(f"Error occurred while initializing PineconeVectorStore: {e}")
    return PineconeVectorStore.from_existing_index(embedding=embedding, index_name=index)


def store_docs(docs: list[Document])-> None:
    vc = get_vector_store()
    batch_size = (int)(os.environ.get("BATCH_SIZE", 80))
    delay = float(os.environ.get("TIME_SLEEP", 30))
    for i in range(0,len(docs), batch_size):
        
        batch = docs[i:i+batch_size]
        
        print(f"\n--- Processing Batch {i // batch_size + 1} ---")
        print(f"Uploading documents {i} to {i + len(batch)}...")
        try:
            vc.add_documents(batch)
            print(f"Batch {i // batch_size + 1} uploaded successfully.")
        except Exception as e:
            print(f"Error occurred while uploading batch {i // batch_size + 1}: {e}")
            print("Retrying after 30s delay...")
            time.sleep(30)
            
            try:
                vc.add_documents(batch)
                print(f"Batch {i // batch_size + 1} uploaded successfully.")
            except Exception as e:
                print(f"Error occurred while uploading batch {i // batch_size + 1}: {e}")
            
        print(f"Waiting for {delay} seconds before processing the next batch...")
        time.sleep(delay)
        
    print("All batches processed.")
    
    
def get_docs_from_file(key: str, chunk_size: int, chunk_overlap: int) -> list[Document] | None:
    
    endpoint_url = os.environ.get("R2_ENDPOINT_URL")
    bucket_name = os.environ.get("R2_BUCKET_NAME")
    access_key_id = os.environ.get("R2_ACCESS_KEY_ID")
    secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    if(not endpoint_url or not bucket_name or not access_key_id or not secret_access_key):
        raise ValueError("R2 credentials not found in environment variables.")
    docs = None
    try: 
        s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key
        )
        
        r2_object = s3_client.get_object(Bucket=bucket_name, Key=key)
        file_bytes = r2_object['Body'].read()
        import tempfile
        filename = key.split("/")[-1]
        temp_file_path = os.path.join(tempfile.gettempdir(), filename)
        with open(temp_file_path, "wb") as f:
            f.write(file_bytes)
        
        docs = main(pdf_path = temp_file_path,chunk_size_tokens=chunk_size,
                    chunk_overlap_tokens=chunk_overlap,pymupdf_pages_per_window=10)
        
        os.remove(temp_file_path)

    except Exception as e:
        print(f"Error occurred while processing file {key}: {e}")
        
    return docs

def generate_embeddings_for_file(file_name: str, chunk_size: int, chunk_overlap: int, userId: str, workspaceId: str) -> None:
    
    print(f"Processing file: {file_name}")
    try: 
        key = f"users/{userId}/{workspaceId}/{file_name}"
        docs: list[Document] | None = get_docs_from_file(key, chunk_size, chunk_overlap)
        if docs is None:
            raise ValueError(f"No documents could be generated for file {file_name}.")
        
        for item in docs:
            item.metadata["fileName"] = file_name
            item.metadata["tenantId"] = userId
            item.metadata["workspaceId"] = workspaceId
        
        store_docs(docs)
        return        
        
    except Exception as e:
        print(f"Error occurred while getting documents from file {file_name}: {e}")
        return

if __name__ == "__main__":
    generate_embeddings_for_file(
        file_name="longwalk.pdf",
        chunk_size=1024,
        chunk_overlap=200,
        userId="user1",
        workspaceId="workspace1"
    )