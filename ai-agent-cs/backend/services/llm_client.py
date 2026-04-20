from google import genai
import ollama
from typing import List, Optional
import logging
import time
from ..config import (
    MAX_OUTPUT_TOKENS,
    GEMINI_API_KEY, GEMINI_API_KEY_FALLBACK, GEMINI_MODEL,
    LLM_PROVIDER, OLLAMA_MODEL, OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL
)

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.provider = LLM_PROVIDER
        logger.info(f"Initializing LLM Client with provider: {self.provider}")
        
        if self.provider == "gemini":
            self.api_keys = []
            if GEMINI_API_KEY:
                self.api_keys.append(GEMINI_API_KEY)
            if GEMINI_API_KEY_FALLBACK:
                self.api_keys.append(GEMINI_API_KEY_FALLBACK)
                
            if not self.api_keys:
                logger.error("No GEMINI_API_KEY is set in environment or config.py")
                raise ValueError("GEMINI_API_KEY missing. Cannot initialize Gemini Client.")
            
            self.current_key_idx = 0
            self.model_name = GEMINI_MODEL
            self._init_gemini_client()
        else:
            # Ollama initialization
            self.model_name = OLLAMA_MODEL
            self.embed_model = OLLAMA_EMBED_MODEL
            self.ollama_client = ollama.Client(host=OLLAMA_BASE_URL)
            logger.info(f"Ollama Client connected to: {OLLAMA_BASE_URL}")

    def _init_gemini_client(self):
        self.gemini_client = genai.Client(api_key=self.api_keys[self.current_key_idx])

    def _rotate_gemini_key(self):
        self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
        logger.warning(f"Rotating to Gemini API key (index {self.current_key_idx})")
        self._init_gemini_client()

    def generate_response(self, prompt: str, context: List[str] = None, system_prompt: Optional[str] = None, **kwargs) -> str:
        if context and len(context) > 0:
            context_str = "\n\n".join(context)
            full_prompt = f"Context documents (Use ONLY if relevant):\n{context_str}\n\nUser Question: {prompt}\n\nInstructions: First, check if the user is asking about [RECENT CHAT HISTORY]. If they are, use the history. Otherwise, use the Context documents and any provided [GLOBAL HOTEL FACTS]. If those sources fully answer the question, answer directly. If the context is completely irrelevant to the question, ignore it."
        else:
            full_prompt = f"User Question: {prompt}\n\nWARNING: No local context docs found. Check if the answer is in the [GLOBAL HOTEL FACTS] or [RECENT CHAT HISTORY]. If it is, answer directly. If not, only then ask a clarifying question to try and narrow down the guest's intent."

        if self.provider == "gemini":
            return self._generate_gemini_response(full_prompt, system_prompt, **kwargs)
        else:
            return self._generate_ollama_response(full_prompt, system_prompt, **kwargs)

    def _generate_gemini_response(self, full_prompt: str, system_prompt: Optional[str], **kwargs) -> str:
        config = {
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "temperature": kwargs.get("temperature", 0.7),
        }
        if system_prompt:
            config["system_instruction"] = system_prompt

        for attempt in range(len(self.api_keys)):
            try:
                response = self.gemini_client.models.generate_content(
                    model=self.model_name,
                    contents=full_prompt,
                    config=config
                )
                return response.text
            except Exception as e:
                logger.error(f"Error generating response with Gemini on key {self.current_key_idx}: {e}")
                if attempt < len(self.api_keys) - 1:
                    self._rotate_gemini_key()
                else:
                    raise

    def _generate_ollama_response(self, full_prompt: str, system_prompt: Optional[str], **kwargs) -> str:
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': full_prompt})

        try:
            response = self.ollama_client.chat(
                model=self.model_name,
                messages=messages,
                options={
                    'temperature': kwargs.get("temperature", 0.7),
                    'num_predict': MAX_OUTPUT_TOKENS,
                }
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise

    def generate_embedding(self, text: str) -> List[float]:
        results = self.generate_embeddings([text])
        if not results:
            raise ValueError("Failed to generate embedding")
        return results[0]

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if self.provider == "gemini":
            return self._generate_gemini_embeddings(texts)
        else:
            return self._generate_ollama_embeddings(texts)

    def _generate_gemini_embeddings(self, texts: List[str]) -> List[List[float]]:
        for attempt in range(len(self.api_keys)):
            try:
                all_embeddings = []
                batch_size = 50
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    response = self.gemini_client.models.embed_content(
                        model="models/text-embedding-004",
                        contents=batch
                    )
                    batch_vectors = [e.values for e in response.embeddings]
                    all_embeddings.extend(batch_vectors)
                    if i + batch_size < len(texts):
                        time.sleep(5.0) 
                return all_embeddings
            except Exception as e:
                logger.error(f"Gemini embeddings failed on attempt {attempt + 1}: {e}")
                if attempt < len(self.api_keys) - 1:
                    self._rotate_gemini_key()
                else:
                    raise

    def _generate_ollama_embeddings(self, texts: List[str]) -> List[List[float]]:
        all_embeddings = []
        try:
            for text in texts:
                response = self.ollama_client.embeddings(
                    model=self.embed_model,
                    prompt=text
                )
                all_embeddings.append(response['embedding'])
            return all_embeddings
        except Exception as e:
            logger.error(f"Ollama embeddings failed: {e}")
            raise

# Global instance
llm_client = LLMClient()
