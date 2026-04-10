import ollama
from google import genai
from typing import List, Optional
import logging
from ..config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, MAX_OUTPUT_TOKENS,
    LLM_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL
)

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self):
        self.client = ollama.Client(host=OLLAMA_BASE_URL)
        self.model = OLLAMA_MODEL

    def generate_response(self, prompt: str, context: List[str] = None, system_prompt: Optional[str] = None, **kwargs) -> str:
        try:
            full_prompt = prompt
            if context and len(context) > 0:
                context_str = "\n\n".join(context)
                full_prompt = f"Context:\n{context_str}\n\nQuestion: {prompt}\n\nIMPORTANT: Answer the question using ONLY the facts from the Context above. Do not add any information that is not explicitly stated in the Context."
            else:
                full_prompt = f"Question: {prompt}\n\nCRITICAL: You have NO context documents available for this question. You MUST NOT guess, invent, or fabricate any facts such as phone numbers, emails, prices, or policies. Instead, politely tell the guest that you don't have that specific information right now and offer to connect them with the front desk staff."

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": full_prompt})

            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={"num_predict": MAX_OUTPUT_TOKENS, **kwargs}
            )
            return response["message"]["content"]
        except Exception as e:
            logger.error(f"Error generating response with Ollama: {e}")
            raise

class GeminiClient:
    def __init__(self):
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY is not set in environment or config.py")
            raise ValueError("GEMINI_API_KEY missing")
        # In 2026, the SDK uses a unified genai.Client
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

class LLMClient:
    def __init__(self):
        self.provider = LLM_PROVIDER
        if self.provider == "GEMINI":
            logger.info(f"Initializing Gemini Client (2026 SDK) with model: {GEMINI_MODEL}")
            self.implementation = GeminiClient()
        else:
            logger.info(f"Initializing Ollama Client with model: {OLLAMA_MODEL}")
            self.implementation = OllamaClient()

    def generate_response(self, *args, **kwargs) -> str:
        return self.implementation.generate_response(*args, **kwargs)

    def generate_embedding(self, text: str) -> List[float]:
        """Note: Project currently uses sentence_transformers in rag_service, so this is rarely used directly."""
        if self.provider == "OLLAMA":
             response = self.implementation.client.embeddings(model=OLLAMA_MODEL, prompt=text)
             return response["embedding"]
        else:
             # Using the 2026 SDK for embeddings if needed
             try:
                 response = self.implementation.client.models.embed_content(
                     model="text-embedding-004",
                     contents=text
                 )
                 return response.embeddings[0].values
             except Exception:
                 logger.warning("Gemini embeddings failed. Fallback to constant.")
                 return [0.0] * 384

# Global instance
llm_client = LLMClient()
