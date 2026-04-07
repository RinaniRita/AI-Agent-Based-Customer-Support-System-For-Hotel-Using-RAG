"""
Agent Router — LLM-Driven Tool-Calling AI Agent
================================================
Uses Ollama to classify user intent, then dispatches to the correct
Python tool (database function).  Falls back to plain Ollama chat
for general questions.

Tools:
    1. get_rooms()              — list every room type from SQLite
    2. recommend_room()         — rooms that fit a budget
    3. book_room()              — kick off the booking flow
    4. check_room_availability  — is room X free right now?
    5. get_room_status          — what is the live status of room X?
    6. check_food_inventory     — is food item Y in stock?
    7. suggest_alternative_food — recommends alternatives if out of stock
    8. get_order_status         — look up food order by ID
"""

import re
import logging
from typing import Dict, Any, List, Optional

from ..services.llm_client import llm_client
from ..services.rag_service import RAGService
from ..config import OLLAMA_BASE_URL, OLLAMA_MODEL

# Database helpers
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.database.db_service import (
    get_connection, create_booking, update_booking_guest_info,
    get_room_info, check_availability, get_active_booking_by_room, get_food_order,
    create_service_request
)

# ── Service Layer (modular, SQLite backed) ──────────────────────
from backend.services.food_service import check_food_inventory, suggest_alternative_food
from backend.services.room_service import check_room_availability, get_room_status
from backend.services.order_service import get_order_status
from backend.services.user_service import get_my_booking_info, check_food_order_permission

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
#  TOOL 4 — request_service
# ──────────────────────────────────────────────
def request_service(telegram_id: int, request_type: str, details: str = "") -> Dict[str, Any]:
    """Log a front desk service request and return the ID."""
    req_id = create_service_request(telegram_id, request_type, details)
    return {
        "request_id": req_id,
        "request_type": request_type,
        "details": details,
        "status": "PENDING"
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
        allowed = ("GET_ROOMS", "RECOMMEND", "BOOK", "ORDER_FOOD", "MY_BOOKING",
                   "FOOD_AVAILABILITY", "ORDER_STATUS", "ROOM_AVAILABILITY", "ROOM_STATUS", "SERVICE_REQUEST", "GENERAL")
        if label not in allowed:
            logger.warning(f"Unexpected intent label '{label}', falling back to GENERAL")
            label = "GENERAL"
        return label
    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        return "GENERAL"


# ──────────────────────────────────────────────
#  EXTRACTORS  (Regex to pull variables from text)
# ──────────────────────────────────────────────
def _extract_budget(text: str) -> Optional[float]:
    """Try to pull a numeric budget from the user's message."""
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

def _extract_room_number(text: str) -> Optional[int]:
    """Extract room number like 'room 101'."""
    m = re.search(r"room\s*#?\s*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{2,4})\b", text)
    return int(m.group(1)) if m else None

def _extract_order_id(text: str) -> Optional[int]:
    """Extract order ID like 'order 5'."""
    m = re.search(r"order\s*#?\s*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,5})\b", text)
    return int(m.group(1)) if m else None

def _extract_food_item(text: str) -> Optional[str]:
    """Scan user message for a known food item from the food_menu SQL table."""
    text_lower = text.lower()
    conn = get_connection()
    rows = conn.execute("SELECT item_name FROM food_menu").fetchall()
    conn.close()
    for row in rows:
        if row["item_name"].lower() in text_lower:
            return row["item_name"]
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

    # ── ROOM_AVAILABILITY ──
    elif intent == "ROOM_AVAILABILITY":
        room_no = _extract_room_number(user_input)
        if not room_no:
            return {
                "response": "I see you're asking about room availability. Could you please provide the room number?",
                "intent": intent, "tool_used": "check_room_availability", "tool_result": None
            }
        booking = get_active_booking_by_room(room_no)
        # If there's an active booking that isn't cancelled, it's booked.
        if booking and booking["status"] != "CANCELLED":
            resp = f"Room {room_no} is already booked at that time."
        else:
            resp = f"Room {room_no} is available at that time."
        return {"response": resp, "intent": intent, "tool_used": "check_room_availability", "tool_result": (room_no, True)}

    # ── ROOM_STATUS ──
    elif intent == "ROOM_STATUS":
        room_no = _extract_room_number(user_input)
        if not room_no:
            return {
                "response": "Could you please specify which room number you'd like the status for?",
                "intent": intent, "tool_used": "get_room_status", "tool_result": None
            }
        booking = get_active_booking_by_room(room_no)
        if not booking or booking["status"] == "CANCELLED":
            resp = f"Room {room_no} is currently available."
        else:
            status = booking["status"].upper().strip()
            if status == "CHECK_IN" or status == "CHECK IN":
                resp = f"Room {room_no} is currently occupied (checked in)."
            elif status == "CHECK_OUT" or status == "CHECK OUT":
                resp = f"Room {room_no} is being prepared after check-out."
            else:
                resp = f"Room {room_no} is currently booked."
            # Maintenance check explicitly omitted as it isn't part of active db flows, but logic is easy to add!
        return {"response": resp, "intent": intent, "tool_used": "get_room_status", "tool_result": room_no}

    # ── ORDER_STATUS ──
    elif intent == "ORDER_STATUS":
        order_id = _extract_order_id(user_input)
        if not order_id:
            return {
                "response": "I'd be happy to check your food status! Could you provide your order number?",
                "intent": intent, "tool_used": "get_order_status", "tool_result": None
            }
        order = get_food_order(order_id)
        if not order:
            resp = "I couldn't find that information. Could you please check the details?"
        else:
            status = order["status"].lower().strip()
            if "pending" in status or "received" in status:
                resp = "Your order is pending."
            elif "preparing" in status or "plating" in status:
                resp = "Your order is being prepared."
            elif "en_route" in status or "delivering" in status:
                resp = "Your order is on the way."
            elif "delivered" in status or "completed" in status:
                resp = "Your order has been delivered."
            elif "cancelled" in status:
                resp = "Your order has been cancelled."
            else:
                resp = "Your order is pending." # Safe fallback
        return {"response": resp, "intent": intent, "tool_used": "get_order_status", "tool_result": order_id}

    # ── FOOD_AVAILABILITY ──
    elif intent == "FOOD_AVAILABILITY":
        item_name = _extract_food_item(user_input)
        if not item_name:
            resp = "I couldn't find that item. Could you try another one?"
        else:
            is_available = check_food_inventory(item_name)
            if is_available:
                resp = f"Yes, we currently have {item_name.title()} available."
            else:
                alts = suggest_alternative_food(item_name)
                alts_str = ", ".join(alts) if alts else "other delicious options on our menu"
                resp = f"Sorry, {item_name.title()} is currently out of stock.\nHowever, you may like: {alts_str}."
        return {"response": resp, "intent": intent, "tool_used": "check_food_inventory", "tool_result": item_name}

    # ── MY_BOOKING ──
    elif intent == "MY_BOOKING":
        booking_info = get_my_booking_info(chat_id)
        if not booking_info:
            resp = (
                "ℹ️ You don't have any active booking linked to your account.\n\n"
                "_Type \"Book a room\" to start a reservation!_"
            )
        else:
            resp = (
                f"📝 *Your Current Booking*\n\n"
                f"🔑 *Booking ID:* #{booking_info['booking_id']}\n"
                f"🛊 *Room:* #{booking_info['room_number']} ({booking_info['room_type']})\n"
                f"📊 *Status:* {booking_info['status_label']}\n"
                f"📅 *Check-in:* {booking_info['check_in'] or 'N/A'}\n"
                f"📅 *Check-out:* {booking_info['check_out'] or 'N/A'}\n"
                f"🌙 *Nights:* {booking_info['nights'] or 'N/A'}\n"
                f"💰 *Total:* €{booking_info['total_price'] or 'N/A'}"
            )
        return {"response": resp, "intent": intent, "tool_used": "get_booking_by_user", "tool_result": booking_info}

    # ── SERVICE_REQUEST ──
    elif intent == "SERVICE_REQUEST":
        # Identify service type from message
        lowered = user_input.lower()
        service_type = "OTHER"
        if "towel" in lowered: service_type = "TOWELS"
        elif "clean" in lowered or "housekeeping" in lowered: service_type = "HOUSEKEEPING"
        elif "pillow" in lowered: service_type = "PILLOWS"
        elif "wake up" in lowered: service_type = "WAKE_UP_CALL"
        
        # Log the request
        result = request_service(chat_id, service_type, user_input)
        
        resp = (
            f"🛎️ *Front Desk Request Logged*\n\n"
            f"I've shared your request with our staff:\n"
            f"📝 *Request:* {user_input}\n\n"
            "Someone will be with you shortly! ✅"
        )
        return {
            "response": resp,
            "intent": intent,
            "tool_used": "request_service",
            "tool_result": result,
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
