from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from langchain_cohere import CohereEmbeddings
from langchain_core.documents import Document
import boto3
from typing import Any
from langchain_community.retrievers import PineconeHybridSearchRetriever

class CustomPineconeHybridSearchRetriever(PineconeHybridSearchRetriever):
    filter_dict: dict = None
    
    def _get_relevant_documents(self, query: str, *, run_manager, **kwargs: Any):
        if self.filter_dict:
            kwargs["filter"] = self.filter_dict
        return super()._get_relevant_documents(query, run_manager=run_manager, **kwargs)

# pyrefly: ignore [missing-import]
from pinecone import Pinecone
import time
import os
from server.app.controllers.main import main
# pyrefly: ignore [missing-import]
from pinecone_text.sparse import BM25Encoder

load_dotenv()

def get_embedding_model():
    cohere_api = os.environ.get("COHERE_API_KEY")
    cohere_model = os.environ.get("COHERE_MODEL")
    if(not cohere_api or not cohere_model):
        raise ValueError("Cohere API key or Cohere model name not found in environment variables.")
    return CohereEmbeddings(cohere_api_key=cohere_api, model=cohere_model)

def get_vector_store(top_k: int = 5, filter: dict = None):
    pinecone_api = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX")
    if(not pinecone_api or not index_name):
        raise ValueError("Pinecone API key or index not found in environment variables.")
    try: 
        embedding = get_embedding_model() 
        # Initialize with default BM25 weights (vital for it to work)
        encoder = BM25Encoder().default()
        
        # The hybrid retriever expects an actual Pinecone Index object, not just the string name
        pc = Pinecone(api_key=pinecone_api)
        index = pc.Index(index_name)
    except Exception as e:
        raise ValueError(f"Error occurred while initializing PineconeHybridSearchRetriever: {e}")
        
    return CustomPineconeHybridSearchRetriever(embeddings=embedding, sparse_encoder=encoder, index=index, top_k=top_k, filter_dict=filter)


def store_docs(docs: list[Document])-> None:
    vc = get_vector_store()
    batch_size = (int)(os.environ.get("BATCH_SIZE", 80))
    delay = float(os.environ.get("TIME_SLEEP", 30))
    for i in range(0,len(docs), batch_size):
        
        batch = docs[i:i+batch_size]
        
        # Hybrid Retriever expects raw strings and dicts, not LangChain Document objects
        texts = [doc.page_content for doc in batch]
        metadatas = [doc.metadata for doc in batch]
        
        print(f"\n--- Processing Batch {i // batch_size + 1} ---")
        print(f"Uploading documents {i} to {i + len(batch)}...")
        try:
            vc.add_texts(texts=texts, metadatas=metadatas)
            print(f"Batch {i // batch_size + 1} uploaded successfully.")
        except Exception as e:
            print(f"Error occurred while uploading batch {i // batch_size + 1}: {e}")
            print("Retrying after 30s delay...")
            time.sleep(30)
            
            try:
                vc.add_texts(texts=texts, metadatas=metadatas)
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

def generate_embeddings_for_file(file_name: str, chunk_size: int, chunk_overlap: int, customerId: str, workspaceId: str) -> None:
    
    print(f"Processing file: {file_name}")
    try: 
        key = f"users/{customerId}/{workspaceId}/{file_name}"
        docs: list[Document] | None = get_docs_from_file(key, chunk_size, chunk_overlap)
        if docs is None:
            raise ValueError(f"No documents could be generated for file {file_name}.")
        
        for item in docs:
            item.metadata["fileName"] = file_name
            item.metadata["customerId"] = customerId
            item.metadata["workspaceId"] = workspaceId
        
        store_docs(docs)
        return        
        
    except Exception as e:
        print(f"Error occurred while getting documents from file {file_name}: {e}")
        return

if __name__ == "__main__":
    generate_embeddings_for_file(
        file_name="lettertogod.pdf",
        chunk_size=1000,
        chunk_overlap=500,
        customerId="user1",
        workspaceId="workspace1"
    )