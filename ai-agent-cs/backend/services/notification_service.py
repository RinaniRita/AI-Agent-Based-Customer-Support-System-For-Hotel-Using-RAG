import logging
import httpx
import json
from ..config import (
    NOTIFY_BOOKING_TOKEN, NOTIFY_BOOKING_CHAT_ID,
    NOTIFY_FOOD_TOKEN, NOTIFY_FOOD_CHAT_ID,
    NOTIFY_REQUEST_TOKEN, NOTIFY_REQUEST_CHAT_ID
)

logger = logging.getLogger(__name__)

async def send_telegram_notification(token: str, chat_id: str, text: str, buttons: list = None):
    """Heavyweight helper to send Telegram messages with optional buttons via httpx."""
    if not token or not chat_id:
        logger.warning("Telegram notification skipped: Token or Chat ID missing.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    if buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, data=payload, timeout=10)
            if resp.status_code != 200:
                logger.error(f"Telegram API error ({resp.status_code}): {resp.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")
        return False

async def notify_employee_booking(booking: dict):
    """Notify Reception Bot about a new confirmed booking with Check-in/out buttons."""
    text = (
        f"🏨 *New Booking Confirmed!* 🏨\n\n"
        f"👤 *Guest:* {booking['guest_name']}\n"
        f"📞 *Phone:* `{booking['guest_phone']}`\n"
        f"📧 *Email:* {booking['guest_email']}\n\n"
        f"🚪 *Room Type:* {booking['display_name']}\n"
        f"📅 *Dates:* {booking['check_in']} to {booking['check_out']}\n"
        f"💰 *Total:* €{booking['total_price']}\n\n"
        f"Actions for Booking #{booking['id']}:"
    )
    
    buttons = [
        [
            {"text": "🛎️ Check-In", "callback_data": f"admin:booking:check_in:{booking['id']}"},
            {"text": "👋 Check-Out", "callback_data": f"admin:booking:check_out:{booking['id']}"}
        ],
        [{"text": "❌ Cancel Booking", "callback_data": f"admin:booking:cancelled:{booking['id']}"}]
    ]
    
    await send_telegram_notification(NOTIFY_BOOKING_TOKEN, NOTIFY_BOOKING_CHAT_ID, text, buttons)

async def notify_employee_food(order: dict):
    """Notify Kitchen Bot about a new food order with status update buttons."""
    # Deserialize items if they are JSON string
    items = order.get("items", "[]")
    if isinstance(items, str):
        try:
            items_list = json.loads(items)
        except:
            items_list = []
    else:
        items_list = items

    items_text = "\n".join([f"• {item['name']} x{item.get('quantity', 1)}" for item in items_list])
    
    text = (
        f"🍳 *New Kitchen Order!* 🍳\n\n"
        f"🚪 *Room:* #{order['room_number']}\n"
        f"📝 *Items:*\n{items_text}\n"
        f"💰 *Total:* €{order['total_price']}\n\n"
        f"Update Order #{order['id']} Status:"
    )
    
    buttons = [
        [
            {"text": "🍳 Preparing", "callback_data": f"admin:food:preparing:{order['id']}"},
            {"text": "🛎️ En Route", "callback_data": f"admin:food:en_route:{order['id']}"}
        ],
        [
            {"text": "✅ Delivered", "callback_data": f"admin:food:delivered:{order['id']}"},
            {"text": "❌ Cancel", "callback_data": f"admin:food:cancelled:{order['id']}"}
        ]
    ]
    
    await send_telegram_notification(NOTIFY_FOOD_TOKEN, NOTIFY_FOOD_CHAT_ID, text, buttons)

async def notify_employee_request(request: dict):
    """Notify Service Bot about a new guest request."""
    text = (
        f"🛎️ *New Service Request* 🛎️\n\n"
        f"🚪 *Room:* #{request.get('room_number', 'Unknown')}\n"
        f"📝 *Request:* {request['details']}\n"
        f"📊 *Category:* {request['request_type']}\n\n"
        f"Manage Request #{request['id']}:"
    )
    
    buttons = [
        [
            {"text": "⚙️ In Progress", "callback_data": f"admin:request:inprogress:{request['id']}"},
            {"text": "✅ Complete", "callback_data": f"admin:request:complete:{request['id']}"}
        ],
        [{"text": "❌ Cancel", "callback_data": f"admin:request:cancelled:{request['id']}"}]
    ]
    
    await send_telegram_notification(NOTIFY_REQUEST_TOKEN, NOTIFY_REQUEST_CHAT_ID, text, buttons)
