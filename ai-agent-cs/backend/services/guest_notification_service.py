import logging
from telegram import Bot
from ..config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

async def notify_guest_status_update(chat_id: int, target_type: str, status: str, details: dict = None):
    """
    Unified service to notify a guest on Telegram about a status change.
    Used by Admin Bots, API, and Google Sheets Sync.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not configured. Cannot notify guest.")
        return False

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    message_text = ""
    status_upper = status.upper().strip().replace(" ", "_")

    if target_type == "booking":
        booking_id = details.get("id", "N/A") if details else "N/A"
        mapping = {
            "CHECK_IN": "🛎️ *Welcome to Apollo Hotel!*\nYou have successfully Checked In to your room. Enjoy your stay!",
            "CHECK_OUT": "👋 *Thank you for staying with us!*\nYour Check Out is complete. Have a safe journey!",
            "CANCELLED": "❌ *Booking Cancelled*\nYour room booking has been successfully cancelled.",
            "PAYMENT_RECEIVED": "✅ *Payment Confirmed*\nWe have received your room payment securely. Thank you!"
        }
        text = mapping.get(status_upper, f"🔔 *Booking Update:* Your status is now: *{status}*")
        message_text = f"✨ *Apollo Hotel Guest Update* ✨\n\n{text}"

    elif target_type == "food_order":
        order_id = details.get("id", "N/A") if details else "N/A"
        mapping = {
            "RECEIVED": "📥 *Order Received*\nYour order has been received by the kitchen.",
            "PREPARING": "🍳 *Chef is Preparing*\nYour Chef is now preparing your delicious meal!",
            "PLATING": "✨ *Plating in Progress*\nThe kitchen is adding the final touches to your order.",
            "EN_ROUTE": "🛎️ *Order En Route*\nYour server is heading to your room now!",
            "DELIVERED": "✅ *Order Delivered!*\nEnjoy your fantastic meal.",
            "CANCELLED": "❌ *Order Cancelled*\nYour food order has been cancelled."
        }
        text = mapping.get(status_upper, f"📦 *Update:* Your order status is now: *{status}*")
        message_text = f"🍽️ *Live Order Tracker* 🍽️\n(Order #{order_id})\n\n{text}"

    elif target_type == "service_request":
        req_id = details.get("id", "N/A") if details else "N/A"
        mapping = {
            "INPROGRESS": "🛠️ *Staff is on the Way*\nA staff member is currently handling your request.",
            "COMPLETE": "✅ *Request Completed*\nYour recent service request has been completed. Thank you!",
            "CANCELLED": "❌ *Request Cancelled*\nYour service request has been cancelled."
        }
        text = mapping.get(status_upper, f"🔔 *Service Update:* Your request status is: *{status}*")
        message_text = f"🛎️ *Front Desk Update* 🛎️\n\n{text}"

    if not message_text:
        return False

    try:
        await bot.send_message(chat_id=chat_id, text=message_text, parse_mode="Markdown")
        logger.info(f"Pushed status update ({target_type}/{status}) to guest {chat_id}")
        return True
    except Exception as e:
        error_str = str(e)
        if "Forbidden" in error_str or "403" in error_str:
            logger.warning(f"Failed to notify guest {chat_id}: Bot is blocked or chat not started. Error: {error_str}")
        else:
            logger.error(f"Failed to push guest notification to {chat_id}: {error_str}")
        return False
