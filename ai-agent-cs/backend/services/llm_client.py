from google import genai
from typing import List, Optional
import logging
import time
from ..config import (
    MAX_OUTPUT_TOKENS,
    GEMINI_API_KEY, GEMINI_API_KEY_FALLBACK, GEMINI_MODEL
)

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.api_keys = []
        if GEMINI_API_KEY:
            self.api_keys.append(GEMINI_API_KEY)
        if GEMINI_API_KEY_FALLBACK:
            self.api_keys.append(GEMINI_API_KEY_FALLBACK)
            
        if not self.api_keys:
            logger.error("No GEMINI_API_KEY is set in environment or config.py")
            raise ValueError("GEMINI_API_KEY missing. Cannot initialize Gemini Client.")
        
        self.current_key_idx = 0
        logger.info(f"Initializing Gemini Client (2026 SDK) with model: {GEMINI_MODEL}")
        self._init_client()
        self.model_name = GEMINI_MODEL

    def _init_client(self):
        self.client = genai.Client(api_key=self.api_keys[self.current_key_idx])

    def _rotate_key(self):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        logger.warning(f"Rotating to Gemini API key (index {self.current_key_idx})")
        self._init_client()

    def generate_response(self, prompt: str, context: List[str] = None, system_prompt: Optional[str] = None, **kwargs) -> str:
        full_prompt = prompt
        if context and len(context) > 0:
            context_str = "\n\n".join(context)
            full_prompt = f"Context documents to ground your answer:\n{context_str}\n\nUser Question: {prompt}\n\nInstructions: Use ONLY the provided context and any provided [GLOBAL HOTEL FACTS]. If those sources fully answer the question (like Wi-Fi, check-in, or location), answer directly and concisely. Only ask a clarifying question if the intent is truly ambiguous and not covered by the facts."
        else:
            full_prompt = f"User Question: {prompt}\n\nWARNING: No local context docs found. Check if the answer is in the [GLOBAL HOTEL FACTS]. If it is, answer directly. If not, only then ask a clarifying question to try and narrow down the guest's intent."

        # Construct the configuration
        config = {
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "temperature": kwargs.get("temperature", 0.7),
        }
        if system_prompt:
            config["system_instruction"] = system_prompt

        for attempt in range(len(self.api_keys)):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config=config
                )
                return response.text
            except Exception as e:
                logger.error(f"Error generating response with Gemini on key {self.current_key_idx}: {e}")
                if attempt < len(self.api_keys) - 1:
                    self._rotate_key()
                else:
                    raise

    def generate_embedding(self, text: str) -> List[float]:
        return self.generate_embeddings([text])[0]

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a list of texts with rate limiting for Gemini free tier."""
        for attempt in range(len(self.api_keys)):
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
                logger.error(f"Gemini embeddings failed on attempt {attempt + 1}: {e}")
                if attempt < len(self.api_keys) - 1:
                    self._rotate_key()
                elif attempt < 2:  # Allow up to 3 tries across keys
                    time.sleep(2)  # Wait before retry
                    continue
                else:
                    logger.error("All embedding attempts failed. Raising exception to prevent invalid indexing.")
                    raise

# Global instance
llm_client = LLMClient()

