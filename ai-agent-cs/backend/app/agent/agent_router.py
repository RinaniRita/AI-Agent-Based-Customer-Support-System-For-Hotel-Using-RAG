"""
Agent Router — LLM-Driven Tool-Calling AI Agent
================================================
Uses Ollama to classify user intent, then dispatches to the correct
Python tool (database function).  Falls back to plain Ollama chat
for general questions.

Tools:
    1. get_rooms()        — list every room type from SQLite
    2. recommend_room()   — rooms that fit a budget
    3. book_room()        — kick off the booking flow
"""

import re
import logging
from typing import Dict, Any, List, Optional

from ..services.llm_client import llm_client
from ..services.rag_service import RAGService
from ..config import OLLAMA_BASE_URL, OLLAMA_MODEL

# Database helpers (already battle-tested in your project)
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from backend.database.db_service import (
    get_connection, create_booking, update_booking_guest_info,
    get_room_info, check_availability
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  TOOL 1 — get_rooms
# ──────────────────────────────────────────────
def get_rooms() -> List[Dict[str, Any]]:
    """Return every room type with its display name and nightly price."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT room_type, display_name, price_per_night, max_occupancy "
        "FROM rooms ORDER BY price_per_night"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────
#  TOOL 2 — recommend_room
# ──────────────────────────────────────────────
def recommend_room(budget: float) -> List[Dict[str, Any]]:
    """Return rooms whose nightly price is at or below *budget*."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT room_type, display_name, price_per_night, max_occupancy "
        "FROM rooms WHERE price_per_night <= ? ORDER BY price_per_night DESC",
        (budget,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────
#  TOOL 3 — book_room  (initiates a booking)
# ──────────────────────────────────────────────
def book_room(telegram_id: int, room_type: str) -> Dict[str, Any]:
    """Create a PENDING booking row and return its id + room info."""
    booking_id = create_booking(telegram_id, room_type)
    room_info = get_room_info(room_type)
    return {
        "booking_id": booking_id,
        "room_type": room_type,
        "display_name": room_info["display_name"] if room_info else room_type,
        "price_per_night": room_info["price_per_night"] if room_info else 0,
    }


# ──────────────────────────────────────────────
#  INTENT CLASSIFIER  (the "Brain")
# ──────────────────────────────────────────────
def _load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "ai_prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

INTENT_PROMPT = _load_prompt("intent_classifier.md")
FALLBACK_PROMPT = _load_prompt("mini_agent_fallback.md")
CUSTOMER_SUPPORT_PROMPT = _load_prompt("customer_support.md")

# Initialize RAG service for GENERAL intent queries
_rag_service = RAGService()


def classify_intent(user_input: str) -> str:
    """Ask Ollama to classify the user's intent into one of four labels."""
    try:
        response = llm_client.client.chat(
            model=llm_client.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict intent classifier. Reply with exactly one word.",
                },
                {
                    "role": "user",
                    "content": INTENT_PROMPT.format(message=user_input),
                },
            ],
            options={"num_predict": 10, "temperature": 0.0},
        )
        raw = response["message"]["content"].strip().upper()
        # Sanitise: take only the first word in case Ollama adds extras
        label = raw.split()[0] if raw else "GENERAL"
        if label not in ("GET_ROOMS", "RECOMMEND", "BOOK", "ORDER_FOOD", "GENERAL"):
            logger.warning(f"Unexpected intent label '{label}', falling back to GENERAL")
            label = "GENERAL"
        return label
    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        return "GENERAL"


# ──────────────────────────────────────────────
#  BUDGET PARSER  (extract number from text)
# ──────────────────────────────────────────────
def _extract_budget(text: str) -> Optional[float]:
    """Try to pull a numeric budget from the user's message."""
    # Match patterns like "under 150", "below 200", "max 100", "budget 180", or just bare numbers near currency words
    patterns = [
        r"(?:under|below|max|budget|within|up\s*to|less\s*than|cheaper\s*than)\s*[€$£]?\s*(\d+(?:\.\d+)?)",
        r"[€$£]\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*(?:eur|euro|euros|usd|dollars|\$|€|£)",
        r"(\d+(?:\.\d+)?)",  # last resort: any number
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return None


# ──────────────────────────────────────────────
#  FORMAT HELPERS  (make tool output human-readable)
# ──────────────────────────────────────────────
def _format_rooms_list(rooms: List[Dict]) -> str:
    """Turn a list of room dicts into a nice Telegram-friendly string."""
    if not rooms:
        return "😞 Sorry, no rooms match your criteria."
    lines = ["🏨 *Available Rooms:*\n"]
    for r in rooms:
        lines.append(
            f"• *{r['display_name']}* — €{r['price_per_night']:.0f}/night "
            f"(up to {r['max_occupancy']} guests)"
        )
    lines.append("\n_Type \"Book me a room\" to start a reservation!_")
    return "\n".join(lines)


def _format_recommendation(rooms: List[Dict], budget: float) -> str:
    """Format budget-filtered rooms."""
    if not rooms:
        return (
            f"😞 Sorry, we don't have any rooms under €{budget:.0f}/night.\n\n"
            "_Try a higher budget, or type \"Show me all rooms\" to see everything._"
        )
    lines = [f"💰 *Rooms under €{budget:.0f}/night:*\n"]
    for r in rooms:
        lines.append(
            f"• *{r['display_name']}* — €{r['price_per_night']:.0f}/night "
            f"(up to {r['max_occupancy']} guests)"
        )
    lines.append("\n_Type \"Book me a room\" to reserve one of these!_")
    return "\n".join(lines)


# ──────────────────────────────────────────────
#  MAIN AGENT LOOP  (Intent → Tool → Response)
# ──────────────────────────────────────────────
def process_agent_query(user_input: str, chat_id: int) -> Dict[str, Any]:
    """
    The core agent function.

    1. Classify intent via Ollama  (the Brain)
    2. Execute the matching tool    (the Hands)
    3. Return a formatted response

    Returns a dict with at least {'response': str, 'intent': str}
    so the caller in main.py can act on the intent if needed.
    """
    intent = classify_intent(user_input)
    logger.info(f"[Agent] Intent for '{user_input[:40]}…' → {intent}")

    # ── GET_ROOMS ──
    if intent == "GET_ROOMS":
        rooms = get_rooms()
        return {
            "response": _format_rooms_list(rooms),
            "intent": intent,
            "tool_used": "get_rooms",
            "tool_result": rooms,
        }

    # ── RECOMMEND ──
    elif intent == "RECOMMEND":
        budget = _extract_budget(user_input)
        if budget is None:
            budget = 200.0  # sensible default
            note = f"\n\n_I didn't catch a specific budget, so I'm showing rooms under €{budget:.0f}._"
        else:
            note = ""
        rooms = recommend_room(budget)
        return {
            "response": _format_recommendation(rooms, budget) + note,
            "intent": intent,
            "tool_used": "recommend_room",
            "tool_result": rooms,
        }

    # ── BOOK ──
    elif intent == "BOOK":
        # We do NOT auto-book here.  Instead we signal main.py to show the
        # existing room-selection keyboard so the guest picks a room type
        # and enters the familiar booking flow.
        return {
            "response": (
                "🛎️ *Great, let's get you booked!*\n\n"
                "Please select a room type below to begin your reservation:"
            ),
            "intent": intent,
            "tool_used": "book_room",
            "tool_result": None,  # main.py will show the room keyboard
        }

    # ── ORDER FOOD ──
    elif intent == "ORDER_FOOD":
        return {
            "response": (
                "🍽️ *Let's get you some food!*\n\n"
                "I'm opening the In-Room Dining menu for you now."
            ),
            "intent": intent,
            "tool_used": "order_food",
            "tool_result": None,
        }

    # ── GENERAL (RAG-grounded response for hotel knowledge) ──
    else:
        # Retrieve relevant context from the knowledge base
        rag_results = _rag_service.retrieve(user_input, top_k=4)
        context_docs = [r['content'] for r in rag_results]

        if context_docs:
            # We have RAG context — generate a grounded response
            logger.info(f"[Agent] GENERAL with {len(context_docs)} RAG docs")
            fallback = llm_client.generate_response(
                prompt=user_input,
                context=context_docs,
                system_prompt=CUSTOMER_SUPPORT_PROMPT,
            )
        else:
            # No relevant docs found — use safety-first fallback
            logger.info("[Agent] GENERAL with no RAG context, using fallback prompt")
            fallback = llm_client.generate_response(
                prompt=user_input,
                context=[],
                system_prompt=FALLBACK_PROMPT,
            )

        return {
            "response": fallback,
            "intent": intent,
            "tool_used": None,
            "tool_result": None,
        }
