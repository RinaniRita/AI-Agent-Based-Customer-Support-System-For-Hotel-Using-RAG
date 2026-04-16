import logging
import asyncio
from telegram import Update, Bot
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from ..config import (
    NOTIFY_BOOKING_TOKEN, NOTIFY_FOOD_TOKEN, NOTIFY_REQUEST_TOKEN
)
from ..database.db_service import (
    update_food_order_status, 
    get_food_order,
    get_booking,
    get_service_request,
    update_service_request_status
)
# We need an update_booking_status in db_service, I will assume it exists or use field update
from ..database.db_service import update_booking_field 
from .guest_notification_service import notify_guest_status_update

logger = logging.getLogger(__name__)

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle status update buttons from any of the 3 admin bots."""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    if len(data) < 4:
        return

    _, target_type, status, target_id = data
    target_id = int(target_id)
    status_display = status.replace("_", " ").title()

    success = False
    chat_id = None

    if target_type == "booking":
        # Update database
        success = update_booking_field(target_id, "status", status.upper())
        if success:
            booking = get_booking(target_id)
            if booking:
                chat_id = booking["telegram_id"]
                await notify_guest_status_update(chat_id, "booking", status.upper(), booking)

    elif target_type == "food":
        # Update database
        order = update_food_order_status(target_id, status.upper())
        if order:
            success = True
            # Food table uses chat_id, standardized here
            chat_id = order.get("chat_id") or order.get("telegram_id")
            if chat_id:
                await notify_guest_status_update(chat_id, "food_order", status.upper(), order)

    elif target_type == "request":
        # Update database
        request = update_service_request_status(target_id, status.upper())
        if request:
            success = True
            # Service table uses telegram_id, standardized here
            chat_id = request.get("telegram_id") or request.get("chat_id")
            if chat_id:
                await notify_guest_status_update(chat_id, "service_request", status.upper(), request)

    if success:
        await query.edit_message_text(
            text=f"{query.message.text}\n\n✅ *Status updated to {status_display}*",
            parse_mode="Markdown",
            reply_markup=None # Remove buttons after action
        )
    else:
        await query.message.reply_text("❌ Failed to update status in database.")

async def start_admin_bots():
    """Build and start the 3 admin bots."""
    apps = []
    
    for token, name in [
        (NOTIFY_BOOKING_TOKEN, "Booking"),
        (NOTIFY_FOOD_TOKEN, "Food"),
        (NOTIFY_REQUEST_TOKEN, "Request")
    ]:
        if token:
            app = Application.builder().token(token).build()
            app.add_handler(CallbackQueryHandler(handle_admin_callback))
            apps.append((app, name))
            logger.info(f"Initialized Admin Bot: {name}")

    if not apps:
        logger.warning("No Admin Bot tokens configured. Admin bots will NOT start.")
        return [], []

    tasks = []
    started_apps = []
    for app, name in apps:
        try:
            await app.initialize()
            await app.start()
            task = asyncio.create_task(app.updater.start_polling())
            tasks.append(task)
            started_apps.append(app)
            logger.info(f"Admin Bot {name} is polling...")
        except Exception as e:
            logger.error(f"Failed to start Admin Bot {name}: {e}")

    return started_apps, tasks
