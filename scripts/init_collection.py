import json
import time
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance

from config import QDRANT_URL, QDRANT_COLLECTION_NAME, QDRANT_MAX_RETRIES, QDRANT_RETRY_DELAY_SECONDS

print(f"Connecting to Qdrant at {QDRANT_URL}...")

qdrant_client = None
for i in range(QDRANT_MAX_RETRIES):
    try:
        qdrant_client = QdrantClient(QDRANT_URL)
        qdrant_client.get_collections()
        print("Qdrant client created and connection successful.")
        break
    except Exception as e:
        print(f"Attempt {i + 1}/{QDRANT_MAX_RETRIES}: Failed to connect to Qdrant: {e}")
        if i < QDRANT_MAX_RETRIES - 1:
            print(f"Retrying in {QDRANT_RETRY_DELAY_SECONDS} seconds...")
            time.sleep(QDRANT_RETRY_DELAY_SECONDS)
        else:
            print("Max retries reached. Could not connect to Qdrant. Exiting.")
            exit(1)

try:
    if qdrant_client.collection_exists(QDRANT_COLLECTION_NAME):
        print(f"Collection {QDRANT_COLLECTION_NAME} already exists. Exiting.")
        exit(0)
except Exception as e:
    print(f"Failed to check if collection exists after establishing connection: {e}")
    exit(1)

print(f"Collection {QDRANT_COLLECTION_NAME} does not exist. Creating...")
qdrant_client.create_collection(
    collection_name=QDRANT_COLLECTION_NAME,
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)
print(f"Collection {QDRANT_COLLECTION_NAME} created.")

print("Loading Payload and Vectors...")
try:
    with open("scripts/startups_demo.json") as fd:
        payload = list(map(json.loads, fd))
    vectors = np.load("scripts/startup_vectors.npy")
except FileNotFoundError as e:
    print(f"Error loading data files: {e}")
    exit(1)

print("Uploading Vectors to Qdrant...")
try:
    qdrant_client.upload_collection(
        collection_name=QDRANT_COLLECTION_NAME,
        vectors=vectors,
        payload=payload,
        ids=None,
        batch_size=256,
        wait=True
    )
    print("Upload complete.")
except Exception as e:
    print(f"Failed to upload data: {e}")
    exit(1)

print("Init collection script finished.")
