import os
import json
import time
from pathlib import Path
from typing import List, Dict

import numpy as np
import faiss
import logging

from ..services.llm_client import llm_client
from .chunk_kb import process_kb_folder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("build_vector_store")


# ---------- CONFIG ----------
KB_FOLDER = Path("static_data/knowledge_base/Apollo_Hotel_KB")
VECTOR_STORE_DIR = Path("data/vector_store")
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
# ----------------------------


def build_faiss_index(vectors: np.ndarray):
    """
    Build and return FAISS index for given vectors (numpy float32).
    """
    d = vectors.shape[1]
    # Standard IndexFlatL2 for simplicity and accuracy
    index = faiss.IndexFlatL2(d)
    index.add(vectors)
    return index


def save_index_and_metadata(index, metadata_list):
    idx_path = VECTOR_STORE_DIR / "faiss_index.index"
    meta_path = VECTOR_STORE_DIR / "metadata.json"

    logger.info("Saving FAISS index to %s", idx_path)
    faiss.write_index(index, str(idx_path))

    logger.info("Saving %d metadata entries to %s", len(metadata_list), meta_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, ensure_ascii=False, indent=2)


def build_from_chunks(chunks: List[Dict]):
    """
    chunks: list of dicts each with keys: id, text, metadata
    """
    logger.info("Generating Gemini embeddings for %d chunks in batches...", len(chunks))
    
    vectors = []
    metadata_list = []
    
    # Extract all text for batching
    all_texts = [c["text"] for c in chunks]
    
    start = time.time()
    try:
        # Use the batch-capable generator we just added to llm_client
        all_vectors = llm_client.generate_embeddings(all_texts)
        
        for i, (text, emb) in enumerate(zip(all_texts, all_vectors)):
            metadata_entry = {
                "id": i,
                "text_snippet": text,
                "metadata": chunks[i].get("metadata", {})
            }
            metadata_list.append(metadata_entry)
            vectors.append(emb)

    except Exception as e:
        logger.error("Batch embedding failed: %s", e)
        raise

    vectors = np.array(vectors, dtype="float32")
    logger.info("Embeddings generated in %.2fs", time.time() - start)

    if vectors.shape[0] == 0:
        raise RuntimeError("No vectors available to build index.")

    index = build_faiss_index(vectors)
    save_index_and_metadata(index, metadata_list)
    logger.info("Vector store build complete. Indexed %d vectors.", vectors.shape[0])


if __name__ == "__main__":
    logger.info("Processing KB folder: %s", KB_FOLDER)
    chunks = process_kb_folder(str(KB_FOLDER))
    logger.info("Total chunks: %d", len(chunks))
    build_from_chunks(chunks)
