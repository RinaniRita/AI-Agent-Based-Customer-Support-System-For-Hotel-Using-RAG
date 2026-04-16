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

# Database helpers
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.database.db_service import (
    get_connection, create_booking, update_booking_guest_info,
    get_room_info, check_availability, get_active_booking_by_room, get_food_order,
    create_service_request, get_all_active_bookings_by_user
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
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Prompt file missing: {filename}. Using empty string as fallback.")
        return ""
    except Exception as e:
        logger.error(f"Error loading prompt {filename}: {e}")
        return ""

INTENT_PROMPT = _load_prompt("intent_classifier.md")
FALLBACK_PROMPT = _load_prompt("mini_agent_fallback.md")
CUSTOMER_SUPPORT_PROMPT = (
    _load_prompt("customer_support.md") + "\n\n" +
    _load_prompt("global_info.md") + "\n\n" +
    _load_prompt("rag_grounding_and_anti_hallucination.md") + "\n\n" +
    _load_prompt("formatting_guidelines_prompt.md")
)
# Note: Safety and Escalation prompts merged into core files to save tokens

# Initialize RAG service for GENERAL intent queries
_rag_service = RAGService()


def classify_intent(user_input: str) -> str:
    """Ask LLM to classify the user's intent into one of predefined labels."""
    try:
        raw_response = llm_client.generate_response(
            prompt=INTENT_PROMPT.format(message=user_input),
            system_prompt="You are a strict intent classifier. Reply with exactly one word.",
            temperature=0.0
        )
        raw = raw_response.strip().upper()
        # Sanitise: split by space OR pipe just in case model is stubborn
        label = re.split(r'[ |]', raw)[0] if raw else "GENERAL"
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
    
    # 1. Look for exact matches in DB
    for row in rows:
        if row["item_name"].lower() in text_lower:
            return row["item_name"]
            
    # 2. Heuristic: If we see "order a/the [X]" or "have [X]", try to grab the noun
    # This helps catch items NOT in our DB so we can say "we don't have that"
    patterns = [
        r"(?:order|have|get|request|want)\s+(?:a|an|the|some)?\s*([a-z\s]+)(?:\?|\.|!|$)",
        r"(?:is|do\s+you\s+have)\s+([a-z\s]+)\s+(?:available|in\s+stock|on\s+the\s+menu)\??"
    ]
    for pat in patterns:
        m = re.search(pat, text_lower)
        if m:
            potential_item = m.group(1).strip()
            # Basic cleaning (remove "is it", "please", etc.)
            potential_item = potential_item.split(" please")[0].split(" is")[0].strip()
            if len(potential_item) > 2 and potential_item not in ["food", "something to eat", "a meal", "dinner", "lunch", "breakfast", "me a meal", "to order food"]:
                return f"UNKNOWN:{potential_item}"
                
    return None


# ──────────────────────────────────────────────
#  FORMAT HELPERS  (make tool output human-readable)
# ──────────────────────────────────────────────
def _format_rooms_list(rooms: List[Dict]) -> str:
    """Turn a list of room dicts into a nice Telegram-friendly string."""
    if not rooms:
        return "😞 I'm sorry, I couldn't find any rooms that match your criteria at the moment."
    
    intro = (
        "🏨 *Welcome to Apollo Hotel Luxury Accommodations!*\n\n"
        "I would be delighted to share our available room categories with you. "
        "Each of our rooms is designed to provide a premium experience:\n"
    )
    lines = [intro]
    for r in rooms:
        lines.append(
            f"• *{r['display_name']}* — €{r['price_per_night']:.0f}/night "
            f"(up to {r['max_occupancy']} guests)"
        )
    lines.append("\n_Type \"Book me a room\" to start your reservation or ask me about any room details!_")
    return "\n".join(lines)


def _format_recommendation(rooms: List[Dict], budget: float) -> str:
    """Format budget-filtered rooms."""
    if not rooms:
        return (
            f"😞 I'm sorry, we don't currently have any rooms under €{budget:.0f}/night available.\n\n"
            "_I recommend trying a slightly higher budget, or type \"Show me all rooms\" to see our full collection._"
        )
    
    intro = (
        f"💰 *Curated Options under €{budget:.0f}/night:*\n\n"
        "I've selected the following rooms that offer exceptional value within your budget:\n"
    )
    lines = [intro]
    for r in rooms:
        lines.append(
            f"• *{r['display_name']}* — €{r['price_per_night']:.0f}/night "
            f"(up to {r['max_occupancy']} guests)"
        )
    lines.append("\n_Would you like to reserve one of these rooms, or should I refine my search further?_")
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
        # Guidance to return to main menu as requested by user
        return {
            "response": (
                "🛎️ *I would be delighted to assist you with your booking!*\n\n"
                "To begin the reservation process and explore our available rooms, please press the button below to **Return to Main Menu**, then select **🏨 Hotel Rooms & Booking**."
            ),
            "intent": intent,
            "tool_used": "book_room",
            "tool_result": None,
        }

    # ── ORDER FOOD ──
    elif intent == "ORDER_FOOD":
        extracted = _extract_food_item(user_input)
        
        # Case A: Found a known item
        if extracted and not extracted.startswith("UNKNOWN:"):
            item_name = extracted
            is_available = check_food_inventory(item_name)
            if is_available:
                resp = (
                    f"🛎️ *Excellent choice!*\n\n"
                    f"Yes, **{item_name.title()}** is currently available. "
                    "I've opened the menu categories below so you can add it to your cart."
                )
            else:
                alts = suggest_alternative_food(item_name)
                alts_str = ", ".join(alts) if alts else "our other fantastic menu items"
                resp = (
                    f"😞 I'm sorry, our **{item_name.title()}** is currently out of stock.\n\n"
                    f"Would you like to try: {alts_str} instead?"
                )
            return {
                "response": resp, "intent": intent, "tool_used": "check_food_inventory", "tool_result": item_name
            }
            
        # Case B: Found a specific request but NOT in our DB
        elif extracted and extracted.startswith("UNKNOWN:"):
            unknown_item = extracted.replace("UNKNOWN:", "").title()
            return {
                "response": (
                    f"🍽️ *Menu Inquiry*\n\n"
                    f"I'm sorry, but **{unknown_item}** is not currently on our menu at Apollo Hotel.\n\n"
                    "Please browse our available categories below to see what else we're serving today!"
                ),
                "intent": intent, "tool_used": None, "tool_result": None
            }

        # Case C: General intent with no specific item found
        return {
            "response": (
                "🍽️ *I would be happy to help you with your dining request!*\n\n"
                "Please press the button below to **Return to Main Menu**, then select **🍽️ Order Room Service** to browse our complete In-Room Dining menu and place your order."
            ),
            "intent": intent, "tool_used": "order_food", "tool_result": None,
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
        # 1. VALIDATION: Check for active bookings
        bookings = get_all_active_bookings_by_user(chat_id)
        
        if not bookings:
            return {
                "response": "😞 I'm sorry, service requests (like towels or cleaning) are available exclusively to our checked-in guests. I couldn't find an active reservation linked to your account.",
                "intent": intent,
                "tool_used": "check_user_bookings",
                "tool_result": "no_booking"
            }

        # 2. HEURISTIC: Did they mention a room number in their request?
        mentioned_room = _extract_room_number(user_input)
        
        # If multiple rooms, and no room was mentioned, we must ask
        if len(bookings) > 1 and not mentioned_room:
            room_list = [str(b['room_number']) for b in bookings]
            return {
                "response": (
                    f"🛎️ *Multiple Rooms Detected*\n\n"
                    f"I see you have multiple active rooms ({', '.join(room_list)}). "
                    "Which room should I send this request to?"
                ),
                "intent": intent,
                "tool_used": "request_room_selection",
                "room_options": room_list, # Will be used by bot_server to show buttons
                "tool_result": "needs_selection"
            }

        # 3. ASSIGN ROOM: Use mentioned room, or the only room available
        target_room = mentioned_room if mentioned_room else bookings[0]['room_number']
        
        # Verify mentioned room belongs to the user
        if target_room not in [b['room_number'] for b in bookings]:
             return {
                "response": f"⚠️ I found your request for Room {target_room}, but I only see bookings for rooms {', '.join(str(b['room_number']) for b in bookings)}. Could you please clarify?",
                "intent": intent,
                "tool_used": "verify_room_ownership",
                "tool_result": "invalid_room"
            }

        # 4. EXECUTE REQUEST
        lowered = user_input.lower()
        service_type = "OTHER"
        if "towel" in lowered: service_type = "TOWELS"
        elif "clean" in lowered or "housekeeping" in lowered: service_type = "HOUSEKEEPING"
        elif "pillow" in lowered: service_type = "PILLOWS"
        elif "wake up" in lowered: service_type = "WAKE_UP_CALL"
        
        # Log the request with the specific room_number
        result = create_service_request(chat_id, service_type, user_input, room_number=target_room)
        
        resp = (
            f"🛎️ *Front Desk Request Successfully Logged*\n\n"
            f"Certainly! I've shared your request with our dedicated staff for **Room {target_room}**:\n"
            f"📝 *Request:* {user_input}\n\n"
            "Our team has been notified and someone will be with you shortly to assist. ✅"
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
            # Dynamic Context Injection for WiFi/Identity
            booking_info = get_my_booking_info(chat_id)
            dynamic_prompt = CUSTOMER_SUPPORT_PROMPT
            if booking_info and booking_info.get('room_number'):
                dynamic_prompt += f"\n\n[GUEST CONTEXT]\nGuest Room Number: {booking_info['room_number']}"
            else:
                dynamic_prompt += f"\n\n[GUEST CONTEXT]\nThe guest currently has no active room assignment."

            # We have RAG context — generate a grounded response
            logger.info(f"[Agent] GENERAL with {len(context_docs)} RAG docs")
            fallback = llm_client.generate_response(
                prompt=user_input,
                context=context_docs,
                system_prompt=dynamic_prompt,
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
