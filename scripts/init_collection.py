import json

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

from config import QDRANT_URL, QDRANT_COLLECTION_NAME

print("Creating Qdrant client...")
qdrant_client = QdrantClient(QDRANT_URL)
qdrant_client.recreate_collection(
    collection_name=QDRANT_COLLECTION_NAME,
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)

print("Loading Payload and Vectors...")
fd = open("scripts/startups_demo.json")
payload = map(json.loads, fd)
vectors = np.load("scripts/startup_vectors.npy")

print("Uploading Vectors to Qdrant...")
qdrant_client.upload_collection(
    collection_name=QDRANT_COLLECTION_NAME,
    vectors=vectors,
    payload=payload,
    ids=None,
    batch_size=256,
)
