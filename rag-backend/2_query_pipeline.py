from typing import Literal
from dotenv import load_dotenv
# from langchain_core.retrievers HybridRetrivers
import os

load_dotenv()

def fetch_context_from_vector_db(query: str,tenantId: str,workspaceId: str,top_k: int = 5,similarity_threshold: float = 0.6) -> str:
    import importlib
    embedding_pipeline = importlib.import_module("1_embedding_pipeline")
    get_vector_store = embedding_pipeline.get_vector_store
    from langchain_community.document_compressors import JinaRerank
    from langchain_classic.retrievers.contextual_compression import ContextualCompressionRetriever
    vc = get_vector_store()
    
    jina_api_key = os.getenv("JINA_API_KEY")
    if not jina_api_key:
        raise ValueError("JINA_API_KEY environment variable is not set.")
    
    reranker = JinaRerank(
        jina_api_key=jina_api_key, 
        model="jina-reranker-v2-base-multilingual", 
        top_n=top_k
    )

    # Wrap your existing vector database retriever
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=reranker, 
        base_retriever=vc.as_retriever(search_kwargs={"tenantId": tenantId, "workspaceId": workspaceId, "top_k": top_k+8})
    )
    try: 
        relevant_docs = compression_retriever.invoke(query)    
    except Exception as e:
        print(f"Error fetching relevant documents: {e}")
        return ""
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    
    return context


    
    