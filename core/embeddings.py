"""
Embedding model factory and ChromaDB vector store management.

Supports two embedding providers:
  - "local"  : sentence-transformers/all-MiniLM-L6-v2  (no API key required)
  - "openai" : text-embedding-3-small  (requires OPENAI_API_KEY)
"""

from __future__ import annotations
from pathlib import Path
from typing import List

import os
import chromadb
from chromadb.config import Settings

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")


def get_embedding_function(provider: str = "local", model_name: str = "all-MiniLM-L6-v2"):
    """Return a ChromaDB-compatible embedding function."""
    if provider == "openai":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        import os
        return OpenAIEmbeddingFunction(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model_name="text-embedding-3-small",
        )
    else:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name=model_name)


def get_or_create_collection(
    chroma_dir: Path,
    collection_name: str,
    embedding_provider: str = "local",
    embedding_model: str = "all-MiniLM-L6-v2",
) -> chromadb.Collection:
    """Get (or create) a persistent ChromaDB collection."""
    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False),
    )
    ef = get_embedding_function(embedding_provider, embedding_model)
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def ingest_chunks(
    collection: chromadb.Collection,
    chunks: List[str],
    doc_id_prefix: str = "chunk",
) -> int:
    """
    Add text chunks to the collection if they haven't been added already.
    Returns number of newly added chunks.
    """
    existing_ids = set(collection.get(include=[])["ids"])
    new_ids, new_docs = [], []

    for i, chunk in enumerate(chunks):
        cid = f"{doc_id_prefix}_{i:04d}"
        if cid not in existing_ids:
            new_ids.append(cid)
            new_docs.append(chunk)

    if new_ids:
        collection.add(documents=new_docs, ids=new_ids)

    return len(new_ids)


def query_collection(
    collection: chromadb.Collection,
    query: str,
    n_results: int = 5,
) -> List[str]:
    """Query the collection and return the top-n matching text chunks."""
    results = collection.query(query_texts=[query], n_results=n_results)
    docs = results.get("documents", [[]])[0]
    return docs
