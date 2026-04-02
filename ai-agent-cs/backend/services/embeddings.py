import ollama
from typing import List, Union
import logging
from app.config import OLLAMA_BASE_URL, OLLAMA_EMBEDDING_MODEL

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self.client = ollama.Client(host=OLLAMA_BASE_URL)
        self.model = OLLAMA_EMBEDDING_MODEL

    def get_embeddings(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Generate embeddings for one or more texts using Ollama.

        Args:
            texts: Single text string or list of text strings

        Returns:
            List of embedding vectors
        """
        try:
            if isinstance(texts, str):
                texts = [texts]

            embeddings = []
            for text in texts:
                response = self.client.embeddings(
                    model=self.model,
                    prompt=text
                )
                embeddings.append(response["embedding"])

            return embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings with Ollama: {e}")
            raise

    def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embeddings = self.get_embeddings([text])
        return embeddings[0]

# Global instance
embedding_service = EmbeddingService()
