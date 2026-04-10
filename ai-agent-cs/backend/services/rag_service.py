import faiss
import numpy as np
from typing import List
import logging
import json
import os

from .llm_client import llm_client
from ..config import (
    VECTOR_STORE_PATH,
    FAISS_INDEX_FILE,
    METADATA_FILE,
)

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        vector_store_path: str = VECTOR_STORE_PATH,
    ):
        """
        Initialize RAG service with Gemini-powered embeddings and FAISS index.
        """
        try:
            self.vector_store_path = vector_store_path
            os.makedirs(self.vector_store_path, exist_ok=True)

            # Gemini text-embedding-004 uses 768 dimensions
            self.dimension = 768
            self.index = faiss.IndexFlatL2(self.dimension)
            self.documents: List[str] = []
            self.metadata: List[dict] = []

            # Try to load existing vector store
            self._load_vector_store()

            logger.info(
                f"RAG service initialized with Gemini Cloud Embeddings, "
                f"store: {self.vector_store_path}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            raise

    def _load_vector_store(self):
        """Load existing vector store if available."""
        index_path = os.path.join(self.vector_store_path, FAISS_INDEX_FILE)
        metadata_path = os.path.join(self.vector_store_path, METADATA_FILE)

        if os.path.exists(index_path) and os.path.exists(metadata_path):
            try:
                # Load FAISS index
                self.index = faiss.read_index(index_path)

                # Load metadata
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata_list = json.load(f)
                    self.metadata = metadata_list
                    # Extract documents from text_snippet
                    self.documents = [item.get('text_snippet', '') for item in metadata_list]

                # Verify dimension match
                if self.index.d != self.dimension:
                    logger.warning(f"Index dimension ({self.index.d}) mismatch with model ({self.dimension}). Index will be reset during next ingestion.")

                logger.info(f"Loaded vector store with {self.index.ntotal} vectors and {len(self.documents)} documents")
            except Exception as e:
                logger.warning(f"Failed to load vector store: {e}")
        else:
            logger.info("No existing vector store found, starting fresh")

    def add_documents(self, docs: List[str], metadata: List[dict] = None):
        """
        Add documents to the vector store using Gemini embeddings.
        """
        if not docs:
            return

        try:
            embeddings_list = []
            for doc in docs:
                emb = llm_client.generate_embedding(doc)
                embeddings_list.append(emb)
            
            embeddings = np.array(embeddings_list).astype(np.float32)
            
            # Check if index matches dimensions
            if self.index.d != embeddings.shape[1]:
                logger.warning("Dimension mismatch. Creating new index.")
                self.dimension = embeddings.shape[1]
                self.index = faiss.IndexFlatL2(self.dimension)

            self.index.add(embeddings)
            self.documents.extend(docs)
            if metadata:
                self.metadata.extend(metadata)
            else:
                self.metadata.extend([{}] * len(docs))
            logger.info(f"Added {len(docs)} documents to index using Gemini")
        except Exception as e:
            logger.error(f"Failed to add documents: {e}")
            raise

    def retrieve(self, query: str, top_k: int = 4, threshold: float = 0.8) -> List[dict]:
        """
        Retrieve relevant documents for a query.
        """
        if len(self.documents) == 0:
            logger.warning("Vector store is empty. Returning empty results.")
            return []
            
        try:
            query_emb_list = llm_client.generate_embedding(query)
            query_emb = np.array([query_emb_list]).astype(np.float32)
            
            distances, indices = self.index.search(query_emb, min(top_k, len(self.documents)))

            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < len(self.documents) and idx != -1:
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