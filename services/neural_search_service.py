import logging
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from config import QDRANT_URL, QDRANT_MODEL_NAME, QDRANT_TOP_K

logger = logging.getLogger(__name__)

try:
    embedding_model = SentenceTransformer(QDRANT_MODEL_NAME)
    logger.info(f"SentenceTransformer model '{QDRANT_MODEL_NAME}' loaded successfully.")
except Exception as e:
    logger.exception(f"Failed to load SentenceTransformer model '{QDRANT_MODEL_NAME}': {e}")
    embedding_model = None


class NeuralSearcher:
    def __init__(self, collection_name: str):
        if not embedding_model:
            raise RuntimeError("Embedding model failed to load. Cannot initialize NeuralSearcher.")
        self.collection_name = collection_name
        self.qdrant_client = QdrantClient(url=QDRANT_URL)
        try:
            self.qdrant_client.get_collection(collection_name=self.collection_name)
            logger.info(f"Successfully connected to Qdrant collection '{self.collection_name}' at {QDRANT_URL}.")
        except Exception as e:
            logger.error(
                f"Could not connect/find Qdrant collection '{self.collection_name}' at {QDRANT_URL}. Error: {e}")
            raise RuntimeError(f"Failed to initialize Qdrant connection: {e}") from e

    def search(self, text: str, top_k: int = QDRANT_TOP_K) -> list[dict]:
        if not embedding_model:
            logger.error("Embedding model not available for search.")
            return []
        try:
            vector = embedding_model.encode(text).tolist()
            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=None,
                limit=top_k,
                with_payload=True
            )
            results = [hit.payload for hit in search_result if hit.payload]
            logger.info(f"Neural search for '{text[:50]}...' with top_k={top_k} returned {len(results)} results.")
            return results
        except Exception as e:
            logger.exception(f"Error during neural search for text '{text[:50]}...': {e}")
            return []
