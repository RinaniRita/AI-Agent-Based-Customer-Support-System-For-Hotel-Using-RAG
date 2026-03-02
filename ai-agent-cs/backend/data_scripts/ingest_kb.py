# ingest_kb.py
"""
Orchestrator: chunk KB -> build vector store.
Run this script from project root (or ensure python path sees backend/data_scripts).
"""

from pathlib import Path
import logging
import sys

# backend/data_scripts is a package; use relative imports if possible
try:
    from .chunk_kb import process_kb_folder
    from .build_vector_store import build_from_chunks
except ImportError:
    # fallback when executed directly as script
    from chunk_kb import process_kb_folder
    from build_vector_store import build_from_chunks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_kb")

KB_ROOT = Path("data/knowledge_base/Luxury_Hotel_KB")
TARGET_SUBFOLDER = "Promotions_and_Support"  # change if you want to ingest other categories

if __name__ == "__main__":
    target = KB_ROOT / TARGET_SUBFOLDER
    if not target.exists():
        logger.error("KB subfolder not found: %s", target)
        sys.exit(1)

    logger.info("Starting ingestion for: %s", target)
    chunks = process_kb_folder(str(target))
    logger.info("Chunks prepared: %d", len(chunks))

    if len(chunks) == 0:
        logger.error("No chunks found. Check your MD files and chunk_kb.py.")
        sys.exit(1)

    logger.info("Building vector store...")
    build_from_chunks(chunks)
    logger.info("Ingestion complete. Vector store saved to data/vector_store/")
