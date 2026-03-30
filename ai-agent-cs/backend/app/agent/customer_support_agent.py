from .agent import BaseAgent
from typing import List
import os

class CustomerSupportAgent(BaseAgent):
    """
    General customer support agent for hotel inquiries.
    """

    def _get_system_prompt(self) -> str:
        prompt_path = os.path.join(os.path.dirname(__file__), "ai_prompts", "customer_support.md")
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "You are a helpful and professional hotel customer support assistant."

    def get_capabilities(self) -> List[str]:
        return [
            "general_inquiries",
            "booking_assistance",
            "amenities_information",
            "policy_explanation",
            "local_area_info"
        ]