import ollama
from typing import List, Optional
import logging
from ..config import OLLAMA_BASE_URL, OLLAMA_MODEL, MAX_OUTPUT_TOKENS

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.client = ollama.Client(host=OLLAMA_BASE_URL)
        self.model = OLLAMA_MODEL

    def generate_response(self, prompt: str, context: List[str] = None, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        Generate a response using the local Ollama model.

        Args:
            prompt: The main prompt/question
            context: List of context strings from RAG retrieval
            system_prompt: Optional system prompt to guide the model's behavior
            **kwargs: Additional parameters

        Returns:
            Generated response string
        """
        try:
            # Combine context with prompt if provided
            full_prompt = prompt
            if context and len(context) > 0:
                context_str = "\n\n".join(context)
                full_prompt = f"Context:\n{context_str}\n\nQuestion: {prompt}\n\nIMPORTANT: Answer the question using ONLY the facts from the Context above. Do not add any information that is not explicitly stated in the Context."
            else:
                full_prompt = f"Question: {prompt}\n\nCRITICAL: You have NO context documents available for this question. You MUST NOT guess, invent, or fabricate any facts such as phone numbers, emails, prices, or policies. Instead, politely tell the guest that you don't have that specific information right now and offer to connect them with the front desk staff."

            # Prepare the messages for chat
            messages = []
            
            # Add system prompt if available
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
                
            messages.append({
                "role": "user",
                "content": full_prompt
            })

            # Generate response
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": MAX_OUTPUT_TOKENS,
                    **kwargs
                }
            )

            return response["message"]["content"]

        except Exception as e:
            logger.error(f"Error generating response with Ollama: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embeddings using Ollama (if supported by the model).

        Note: Not all Ollama models support embeddings. You might need a separate embedding service.

        Args:
            text: Text to embed

        Returns:
            List of embedding floats
        """
        try:
            # Note: This assumes the model supports embeddings
            # If not, you'll need to use a different embedding service
            response = self.client.embeddings(
                model=self.model,
                prompt=text
            )
            return response["embedding"]
        except Exception as e:
            logger.error(f"Error generating embedding with Ollama: {e}")
            # Fallback: return empty list or raise
            raise ValueError(f"Embedding generation failed: {e}")

# Global instance
llm_client = LLMClient()
