from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from typing import List
import logging
import json
import os

from ..config import (
    OLLAMA_EMBEDDING_MODEL,
    VECTOR_STORE_PATH,
    FAISS_INDEX_FILE,
    METADATA_FILE,
)

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        embedding_model: str = OLLAMA_EMBEDDING_MODEL,
        vector_store_path: str = VECTOR_STORE_PATH,
    ):
        """
        Initialize RAG service with embedding model and FAISS index.

        Args:
            embedding_model: Name of the SentenceTransformer model
            vector_store_path: Path to the vector store directory
        """
        try:
            self.vector_store_path = vector_store_path
            os.makedirs(self.vector_store_path, exist_ok=True)

            self.embedder = SentenceTransformer(embedding_model)
            # Dimension should match the embedding model; 384 is common for MiniLM.
            # If you change models, adjust or infer as needed.
            self.dimension = 384
            self.index = faiss.IndexFlatL2(self.dimension)
            self.documents: List[str] = []
            self.metadata: List[dict] = []

            # Try to load existing vector store
            self._load_vector_store()

            logger.info(
                f"RAG service initialized with model: {embedding_model}, "
                f"store: {self.vector_store_path}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            raise

    def _load_vector_store(self):
        """Load existing vector store if available."""
        index_path = os.path.join(self.vector_store_path, FAISS_INDEX_FILE)
        embeddings_path = os.path.join(self.vector_store_path, "embeddings.npy")
        metadata_path = os.path.join(self.vector_store_path, METADATA_FILE)

        if os.path.exists(index_path) and os.path.exists(embeddings_path) and os.path.exists(metadata_path):
            try:
                # Load FAISS index
                self.index = faiss.read_index(index_path)

                # Load metadata
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata_list = json.load(f)
                    self.metadata = metadata_list
                    # Extract documents from text_snippet
                    self.documents = [item.get('text_snippet', '') for item in metadata_list]

                logger.info(f"Loaded vector store with {self.index.ntotal} vectors and {len(self.documents)} documents")
            except Exception as e:
                logger.warning(f"Failed to load vector store: {e}")
        else:
            logger.info("No existing vector store found, starting fresh")

    def add_documents(self, docs: List[str], metadata: List[dict] = None):
        """
        Add documents to the vector store.

        Args:
            docs: List of document chunks
            metadata: Optional list of metadata dicts for each document
        """
        if not docs:
            return

        try:
            embeddings = self.embedder.encode(docs)
            self.index.add(embeddings.astype(np.float32))
            self.documents.extend(docs)
            if metadata:
                self.metadata.extend(metadata)
            else:
                self.metadata.extend([{}] * len(docs))
            logger.info(f"Added {len(docs)} documents to index")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def retrieve(self, query: str, top_k: int = 4, threshold: float = 1.5) -> List[dict]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: Search query
            top_k: Number of top results to return
            threshold: Similarity threshold (lower is more similar)

        Returns:
            List of dicts with 'content', 'score', and 'metadata'
        """
        if len(self.documents) == 0:
            logger.warning("Vector store is empty. Returning empty results.")
            return []
            
        try:
            query_emb = self.embedder.encode([query]).astype(np.float32)
            distances, indices = self.index.search(query_emb, min(top_k, len(self.documents)))

            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < len(self.documents) and dist <= threshold:
                    results.append({
                        'content': self.documents[idx],
                        'score': float(dist),
                        'metadata': self.metadata[idx]
                    })

            logger.info(f"Retrieved {len(results)} documents for query: {query[:50]}...")
            return results
        except Exception as e:
            logger.error(f"Failed to retrieve documents: {e}")
            return []

    def save_index(self, filepath: str):
        """Save the FAISS index to disk."""
        faiss.write_index(self.index, filepath)
        logger.info(f"Index saved to {filepath}")

    def load_index(self, filepath: str):
        """Load the FAISS index from disk."""
        self.index = faiss.read_index(filepath)
        logger.info(f"Index loaded from {filepath}")

    def get_stats(self) -> dict:
        """Get statistics about the index."""
        return {
            'total_documents': len(self.documents),
            'index_size': self.index.ntotal,
            'dimension': self.dimension
        }