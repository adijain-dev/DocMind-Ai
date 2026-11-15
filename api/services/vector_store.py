"""
vector_store.py — Local ChromaDB (fast!) instead of Pinecone (slow cloud)

Speed comparison:
  Pinecone cloud query : 500-1500ms  (network roundtrip)
  ChromaDB local query :   5-  50ms  (in-process, no network!)
"""

import os
import re
import time
import chromadb
from sentence_transformers import SentenceTransformer

try:
    from config import CHROMA_DB_PATH
except ImportError:
    try:
        from ..config import CHROMA_DB_PATH
    except ImportError:
        CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "chroma_db")

# Ensure directory exists
os.makedirs(CHROMA_DB_PATH, exist_ok=True)

# ─── One-time model load ──────────────────────────────────────────────────────
print("[vector_store] Loading embedding model...", flush=True)
_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("[vector_store] Embedding model ready ✓", flush=True)

# ─── Local ChromaDB — persistent client with absolute path ────────────────────
_chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _clean_name(name: str) -> str:
    """ChromaDB collection name: 3-63 chars, letters/digits/hyphens only."""
    if not name:
        return "def"
    cleaned = re.sub(r'[^a-zA-Z0-9-]', '-', name)
    cleaned = re.sub(r'-{2,}', '-', cleaned).strip('-').lower()
    cleaned = cleaned[:63]
    if len(cleaned) < 3:
        cleaned = (cleaned + "---")[:3]
    return cleaned


def _get_collection(api_name: str):
    return _chroma_client.get_or_create_collection(
        name=_clean_name(api_name),
        metadata={"hnsw:space": "cosine"}
    )


def _embed(text: str) -> list:
    return _embedding_model.encode(text[:8000]).tolist()


# ─── Public functions (same interface as before) ──────────────────────────────

def store_document_chunks(chunks, api_name, source_filename):
    """Store document chunks in local ChromaDB."""
    collection = _get_collection(api_name)
    timestamp  = str(int(time.time()))

    ids = []; embeddings = []; documents = []; metadatas = []

    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        ids.append(f"{source_filename}_{timestamp}_{i}")
        embeddings.append(_embed(chunk))
        documents.append(chunk)
        metadatas.append({"source_file": source_filename, "api_name": api_name, "chunk_index": i})

    if not ids:
        return 0

    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    return len(ids)


def find_relevant_chunks(question, api_name, how_many=3):
    """Find most relevant chunks — local cosine similarity, no network!"""
    collection = _get_collection(api_name)
    if collection.count() == 0:
        return []
    n = min(how_many, collection.count())
    results = collection.query(query_embeddings=[_embed(question)], n_results=n, include=["documents"])
    return results["documents"][0] if results["documents"] else []


def get_all_api_names():
    """Return list of all API names stored locally."""
    names = []
    for c in _chroma_client.list_collections():
        c_name = getattr(c, "name", str(c))
        if c_name not in ("def", "default"):
            names.append(c_name)
    return names


def delete_api_documents(api_name):
    """Delete all documents for a specific API."""
    try:
        _chroma_client.delete_collection(_clean_name(api_name))
        return True
    except Exception:
        return False


# ─── Kept for compatibility (not used anymore) ────────────────────────────────
def get_or_create_index():
    return None

def clean_namespace_name(name):
    return _clean_name(name)

def get_text_embedding(text):
    return _embed(text)
