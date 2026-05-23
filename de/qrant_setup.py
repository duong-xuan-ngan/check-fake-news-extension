from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host="localhost", port=6333)

client.recreate_collection(
    collection_name="claim_cache",
    vectors_config=VectorParams(
        size=384,        # must match the embedding model — agree with Backend
        distance=Distance.COSINE,
    ),
)
print("[qdrant] Collection 'claim_cache' created.")