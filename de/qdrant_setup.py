from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host="qdrant", port=6333)
collection_name = "claim_cache"

if not client.collection_exists(collection_name = collection_name):

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=384,        # must match the embedding model — agree with Backend
            distance=Distance.COSINE,
        ),
    )
    print("[qdrant] Collection 'claim_cache' created.")
else:
    print(f"[qdrant] Collection '{collection_name}' already exists. Skipping creation.")