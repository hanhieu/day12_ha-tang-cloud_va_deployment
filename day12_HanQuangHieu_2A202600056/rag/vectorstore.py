import os

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from config import settings

CHROMA_PATH = settings.chroma_path
COLLECTION_NAME = settings.collection_name

_collection = None


def get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        embedding_fn = OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key,
            model_name="text-embedding-3-small",
        )
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
    return _collection
