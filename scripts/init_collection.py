import json

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

from config import QDRANT_URL, QDRANT_COLLECTION_NAME

print("Creating Qdrant client...")
try:
    qdrant_client = QdrantClient(QDRANT_URL)
except Exception as e:
    print(f"Failed to create Qdrant client: {e}")
    exit(1)

try:
    if qdrant_client.collection_exists(QDRANT_COLLECTION_NAME):
        print(f"Collection {QDRANT_COLLECTION_NAME} already exists. Exiting.")
        exit(0)
except Exception as e:
    print(f"Failed to check if collection exists: {e}")
    exit(1)

qdrant_client.create_collection(
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
