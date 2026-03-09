from abc import ABC, abstractmethod
from typing import Dict, Any, List
import logging
from ..services.llm_client import LLMClient
from ..services.rag_service import RAGService

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    Base class for AI agents in the hotel support system.
    """

    def __init__(self, name: str, llm_client: LLMClient, rag_service: RAGService):
        self.name = name
        self.llm_client = llm_client
        self.rag_service = rag_service
        self.system_prompt = self._get_system_prompt()

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass

    def process_query(self, user_query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a user query and return a response.

        Args:
            user_query: The user's question or request
            context: Additional context (e.g., user history, session data)

        Returns:
            Dict with 'response', 'confidence', 'needs_escalation', etc.
        """
        try:
            # Retrieve relevant context from RAG
            rag_results = self.rag_service.retrieve(user_query, top_k=4)
            context_docs = [result['content'] for result in rag_results]

            # Build prompt with context
            full_prompt = f"{self.system_prompt}\n\nUser Query: {user_query}"

            if context_docs:
                context_str = "\n\n".join(context_docs)
                full_prompt += f"\n\nRelevant Information:\n{context_str}"

            # Generate response
            response = self.llm_client.generate_response(full_prompt, context_docs)

            # Determine confidence and escalation need
            confidence = self._calculate_confidence(response, rag_results)
            needs_escalation = self._should_escalate(response, confidence, context)

            return {
                'response': response,
                'confidence': confidence,
                'needs_escalation': needs_escalation,
                'rag_results': rag_results,
                'agent': self.name
            }

        except Exception as e:
            logger.error(f"Error processing query with {self.name}: {e}")
            return {
                'response': "I'm sorry, I encountered an error. Please try again or contact human support.",
                'confidence': 0.0,
                'needs_escalation': True,
                'error': str(e),
                'agent': self.name
            }

    def _calculate_confidence(self, response: str, rag_results: List[dict]) -> float:
        """
        Calculate confidence score based on response and retrieved context.
        """
        # Simple heuristic: higher confidence if more relevant docs found
        base_confidence = min(len(rag_results) / 4.0, 1.0)  # Max 4 docs

        # Adjust based on response length and specificity
        if len(response) < 50:
            base_confidence *= 0.7  # Short responses less confident

        # Check for uncertainty indicators
        uncertainty_words = ['not sure', 'uncertain', 'don\'t know', 'contact']
        if any(word in response.lower() for word in uncertainty_words):
            base_confidence *= 0.8

        return round(base_confidence, 2)

    def _should_escalate(self, response: str, confidence: float, context: Dict[str, Any]) -> bool:
        """
        Determine if the query should be escalated to human support.
        """
        # Escalate if confidence is low
        if confidence < 0.5:
            return True

        # Escalate for sensitive topics
        sensitive_topics = ['complaint', 'refund', 'cancel', 'emergency', 'medical']
        if any(topic in response.lower() or topic in str(context).lower() for topic in sensitive_topics):
            return True

        return False

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Return list of capabilities this agent handles."""
        pass