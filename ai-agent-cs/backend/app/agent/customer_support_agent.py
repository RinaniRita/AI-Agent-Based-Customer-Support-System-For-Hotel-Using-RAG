from .agent import BaseAgent
from typing import List

class CustomerSupportAgent(BaseAgent):
    """
    General customer support agent for hotel inquiries.
    """

    def _get_system_prompt(self) -> str:
        return """You are a helpful and professional hotel customer support assistant for Luxury Hotel.

Your role is to:
- Provide accurate information about hotel services, policies, and amenities
- Assist with booking inquiries and general questions
- Be polite, friendly, and efficient
- Use the provided context to give specific, relevant answers
- If you don't have enough information, suggest contacting human support

Always maintain a welcoming tone and focus on guest satisfaction."""

    def get_capabilities(self) -> List[str]:
        return [
            "general_inquiries",
            "booking_assistance",
            "amenities_information",
            "policy_explanation",
            "local_area_info"
        ]