from pinecone import Pinecone
from dotenv import load_dotenv
import os
load_dotenv()
pinecone_api = os.environ.get("PINECONE_API_KEY","")
index_name = os.environ.get("PINECONE_INDEX","")
pc = Pinecone(api_key=pinecone_api)

index = pc.Index(index_name)

for ids in index.list(namespace=""):

    for vector_id in ids:

        index.update(
            id=vector_id,
            namespace="",
            set_metadata={
                "customerId": "user1",
            }
        )
