from google import genai
from typing import List, Optional
import logging
import time
from ..config import (
    MAX_OUTPUT_TOKENS,
    GEMINI_API_KEY, GEMINI_MODEL
)

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY is not set in environment or config.py")
            raise ValueError("GEMINI_API_KEY missing. Cannot initialize Gemini Client.")
        
        logger.info(f"Initializing Gemini Client (2026 SDK) with model: {GEMINI_MODEL}")
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model_name = GEMINI_MODEL

    def generate_response(self, prompt: str, context: List[str] = None, system_prompt: Optional[str] = None, **kwargs) -> str:
        try:
            full_prompt = prompt
            if context and len(context) > 0:
                context_str = "\n\n".join(context)
                full_prompt = f"Context documents to ground your answer:\n{context_str}\n\nUser Question: {prompt}\n\nInstructions: Use ONLY the provided context. If the answer is not in the context, say you don't know and offer staff assistance."
            else:
                full_prompt = f"User Question: {prompt}\n\nWARNING: No local context docs found. Do not hallucinate. State that you don't have this info and offer front desk help."

            # Construct the configuration
            config = {
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "temperature": kwargs.get("temperature", 0.7),
            }
            if system_prompt:
                config["system_instruction"] = system_prompt

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=config
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating response with Gemini: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        return self.generate_embeddings([text])[0]

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a list of texts with rate limiting for Gemini free tier."""
        try:
            all_embeddings = []
            batch_size = 50
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = self.client.models.embed_content(
                    model="models/gemini-embedding-001",
                    contents=batch
                )
                
                # Extract the list of embeddings
                batch_vectors = [e.values for e in response.embeddings]
                all_embeddings.extend(batch_vectors)
                
                if i + batch_size < len(texts):
                    time.sleep(5.0) # Delay for free tier stability
            
            return all_embeddings
        except Exception as e:
            logger.error(f"Gemini embeddings failed: {e}")
            # Return zero-vectors of size 768 on total failure
            return [[0.0] * 768] * len(texts)

# Global instance
llm_client = LLMClient()

