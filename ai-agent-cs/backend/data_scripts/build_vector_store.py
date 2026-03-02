# build_vector_store.py
"""
Build a FAISS vector index from chunk objects produced by chunk_kb.process_kb_folder.
Saves:
 - data/vector_store/faiss_index.index
 - data/vector_store/metadata.json
 - data/vector_store/embeddings.npy  (optional, for debugging)
"""

import os
import json
import time
from pathlib import Path
from typing import List, Dict

import numpy as np
import faiss
import logging

# Try Gemini (Google Generative AI) and sentence-transformers fallback
try:
    import google.generativeai as genai
except Exception:
    genai = None

# optional fallback
try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

# package import of sibling module (data_scripts is now a package)
try:
    from .chunk_kb import process_kb_folder
except ImportError:
    # allow running as a script (without package context)
    from chunk_kb import process_kb_folder


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("build_vector_store")


# ---------- CONFIG ----------
KB_FOLDER = Path("data/knowledge_base/Luxury_Hotel_KB/Promotions_and_Support")
VECTOR_STORE_DIR = Path("data/vector_store")
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

GEMINI_EMBED_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "models/embedding-001")  # can be overridden by env
SF_MODEL_NAME = "all-MiniLM-L6-v2"  # fallback
TOP_K = 4
# ----------------------------


def get_gemini_embedding(text: str) -> List[float]:
    if genai is None:
        raise RuntimeError("google-generativeai package not installed / not available.")
    # configure API key if not already done
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    # note: embeddings.create returns a response with data[0].embedding
    resp = genai.embeddings.create(model=GEMINI_EMBED_MODEL, input=text)
    return resp.data[0].embedding


# fallback using sentence-transformers local model
_local_st_model = None


def get_local_embedding(text: str) -> List[float]:
    global _local_st_model
    if SentenceTransformer is None:
        raise RuntimeError("sentence-transformers not installed.")
    if _local_st_model is None:
        logger.info("Loading local sentence-transformers model...")
        _local_st_model = SentenceTransformer(SF_MODEL_NAME)
    vec = _local_st_model.encode([text], show_progress_bar=False)[0]
    return vec.tolist()


def get_embedding(text: str) -> List[float]:
    """
    Try Gemini embeddings first; if unavailable, try local sentence-transformers.
    """
    # prefer Gemini if configured
    try:
        if genai is not None and os.environ.get("GEMINI_API_KEY"):
            return get_gemini_embedding(text)
    except Exception as e:
        logger.warning("Gemini embedding failed: %s", str(e))

    # fallback
    try:
        return get_local_embedding(text)
    except Exception as e:
        logger.error("Local embedding failed: %s", str(e))
        # final fallback: deterministic pseudo-embedding (not ideal for production)
        import hashlib
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = np.frombuffer(h, dtype=np.uint8).astype("float32")
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()

def build_faiss_index(vectors: np.ndarray, metric: str = "cosine"):
    """
    Build and return FAISS index for given vectors (numpy float32).
    We'll normalize for cosine similarity and use inner product.
    """
    d = vectors.shape[1]
    # Normalize vectors to unit length for cosine similarity via inner product
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(d)
    index.add(vectors)
    return index


def save_index_and_metadata(index, vectors, metadata_list):
    idx_path = VECTOR_STORE_DIR / "faiss_index.index"
    meta_path = VECTOR_STORE_DIR / "metadata.json"
    emb_path = VECTOR_STORE_DIR / "embeddings.npy"

    logger.info("Saving FAISS index to %s", idx_path)
    faiss.write_index(index, str(idx_path))

    logger.info("Saving %d metadata entries to %s", len(metadata_list), meta_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, ensure_ascii=False, indent=2)

    logger.info("Saving embeddings to %s", emb_path)
    np.save(str(emb_path), vectors)


def build_from_chunks(chunks: List[Dict]):
    """
    chunks: list of dicts each with keys: id, text, metadata
    """
    logger.info("Generating embeddings for %d chunks", len(chunks))
    vectors = []
    metadata_list = []

    start = time.time()
    for i, c in enumerate(chunks):
        text = c["text"]
        meta = c.get("metadata", {})
        try:
            emb = get_embedding(text)
        except Exception as e:
            logger.error("Embedding failed for chunk %s: %s", c["id"], e)
            continue

        vectors.append(emb)
        metadata_entry = {
            "id": c["id"],
            "text_snippet": text[:300],
            "metadata": meta
        }
        metadata_list.append(metadata_entry)

    vectors = np.array(vectors, dtype="float32")
    logger.info("Embeddings generated in %.2fs", time.time() - start)

    if vectors.shape[0] == 0:
        raise RuntimeError("No vectors available to build index.")

    index = build_faiss_index(vectors)
    save_index_and_metadata(index, vectors, metadata_list)
    logger.info("Vector store build complete. Indexed %d vectors.", vectors.shape[0])


if __name__ == "__main__":
    logger.info("Processing KB folder: %s", KB_FOLDER)
    chunks = process_kb_folder(str(KB_FOLDER))
    logger.info("Total chunks: %d", len(chunks))
    build_from_chunks(chunks)
