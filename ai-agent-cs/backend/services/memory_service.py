import redis
import json
import logging
from typing import Any, Optional
from ..config import REDIS_HOST, REDIS_PORT, REDIS_DB

logger = logging.getLogger(__name__)

class MemoryService:
    """
    Service for persistent conversation state and session management using Redis.
    """
    def __init__(self):
        try:
            self.client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_timeout=5
            )
            # Verify connection
            self.client.ping()
            self.is_active = True
            logger.info(f"Redis connected at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            self.is_active = False
            logger.warning(f"Redis connection failed: {e}. Falling back to in-memory storage.")
            self._fallback_storage = {}

    def get(self, key: str) -> Optional[Any]:
        """Retrieve data from Redis or fallback."""
        if not self.is_active:
            return self._fallback_storage.get(key)
        
        data = self.client.get(key)
        if data:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
        return None

    def set(self, key: str, value: Any, expire: int = 86400):
        """Store data in Redis or fallback."""
        if not self.is_active:
            self._fallback_storage[key] = value
            return

        serialized = json.dumps(value)
        self.client.set(key, serialized, ex=expire)

    def delete(self, key: str):
        """Delete data from Redis or fallback."""
        if not self.is_active:
            self._fallback_storage.pop(key, None)
            return
            
        self.client.delete(key)

    def get_chat_history(self, session_id: str) -> list:
        """Retrieve recent chat history for a given session."""
        key = f"chat_history:{session_id}"
        history = self.get(key)
        if hasattr(history, 'encode') and isinstance(history, str):
            try:
                history = json.loads(history)
            except Exception:
                pass
        return history if isinstance(history, list) else []

    def append_to_chat_history(self, session_id: str, role: str, content: str, max_history: int = 10):
        """Append a message to the chat history, capping the list to max_history."""
        key = f"chat_history:{session_id}"
        history = self.get_chat_history(session_id)
        
        history.append({"role": role, "content": content})
        
        # Keep only the last max_history items to prevent context bloat
        if len(history) > max_history:
            history = history[-max_history:]
            
        # Store back in redis (expire in 2 hours / 7200 seconds to save memory)
        self.set(key, history, expire=7200)

# Global instance
memory_service = MemoryService()
