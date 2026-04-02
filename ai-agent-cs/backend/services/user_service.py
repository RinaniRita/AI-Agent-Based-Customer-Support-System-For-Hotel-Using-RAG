"""
user_service.py — User-Based Access Control Service
====================================================
All functions identify users strictly by their Telegram ID.
No cross-user data is ever exposed.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.database.db_service import (
    get_booking_by_user, validate_user_booking, can_order_food
)


def get_my_booking_info(user_id: int) -> dict | None:
    """
    Returns a clean, safe summary of the user's active booking.
    Never exposes other users' data.
    """
    booking = get_booking_by_user(user_id)
    if not booking:
        return None

    status = booking["status"].upper().strip()
    status_label_map = {
        "CONFIRMED": "Confirmed ✅",
        "CHECK_IN": "Checked In 🛎️",
        "CHECK IN": "Checked In 🛎️",
        "PENDING_PAYMENT": "Pending Payment 💳",
        "PAYMENT_RECEIVED": "Payment Received ✅",
        "PAYMENT RECEIVED": "Payment Received ✅",
        "CHECK_OUT": "Checked Out 👋",
        "CHECK OUT": "Checked Out 👋",
        "CANCELLED": "Cancelled ❌",
    }

    return {
        "booking_id": booking["id"],
        "room_number": booking["room_number"],
        "room_type": booking["display_name"],
        "status": booking["status"],
        "status_label": status_label_map.get(status, booking["status"]),
        "check_in": booking.get("check_in"),
        "check_out": booking.get("check_out"),
        "nights": booking.get("nights"),
        "total_price": booking.get("total_price"),
        "guest_name": booking.get("guest_name"),
    }


def check_food_order_permission(user_id: int) -> dict:
    """
    Returns a result dict with 'allowed' (bool) and 'reason' (str).
    Enforces strict CHECK_IN-only food ordering policy.
    """
    booking = get_booking_by_user(user_id)

    if not booking:
        return {
            "allowed": False,
            "reason": "no_booking",
            "message": "You don't have an active booking. Please make a reservation first.",
            "booking": None,
        }

    status = booking["status"].upper().strip()
    if status not in ("CHECK_IN", "CHECK IN"):
        return {
            "allowed": False,
            "reason": "not_checked_in",
            "message": (
                f"Your booking (Room {booking['room_number']}) status is *{booking['status']}*. "
                "You can only order food after you have officially checked in. 🛎️"
            ),
            "booking": booking,
        }

    return {
        "allowed": True,
        "reason": "ok",
        "message": "Access granted.",
        "booking": booking,
    }
