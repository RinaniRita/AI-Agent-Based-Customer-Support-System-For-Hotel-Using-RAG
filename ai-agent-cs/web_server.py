"""
FastAPI web server for serving booking APIs to a static frontend (e.g. GitHub Pages).
Runs alongside the Telegram bot on a separate port.
"""
import os
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Bot
import httpx

# Import database service
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.database.db_service import (
    get_booking, confirm_booking, init_db, update_food_order_status, 
    get_active_food_orders, update_booking_field, update_food_order_field
)
from backend.app.config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

app = FastAPI(title="Luxury Hotel API")

# Enable CORS for GitHub pages frontend!
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rinanirita.github.io",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "ngrok-skip-browser-warning"],
)

@app.on_event("startup")
async def startup():
    """Ensure database is initialized on server start."""
    init_db()
    logger.info("FastAPI JSON API server started.")

class ConfirmRequest(BaseModel):
    booking_id: int

class OrderUpdate(BaseModel):
    order_id: int
    chat_id: int
    status: str

@app.get("/api/booking/{id}")
async def get_booking_details(id: int):
    """Return booking details as JSON for the static frontend."""
    booking = get_booking(id)
    if not booking:
        return JSONResponse({"error": "Booking not found"}, status_code=404)

    return {
        "id": booking["id"],
        "display_name": booking["display_name"],
        "room_number": booking["room_number"],
        "check_in": booking["check_in"],
        "check_out": booking["check_out"],
        "nights": booking["nights"],
        "price_per_night": booking["price_per_night"],
        "total_price": booking["total_price"],
        "guest_name": booking["guest_name"],
        "guest_email": booking["guest_email"],
        "guest_phone": booking["guest_phone"],
        "status": booking["status"]
    }

@app.post("/api/booking/confirm")
async def process_confirm_payment(data: ConfirmRequest):
    """Process payment confirmation and update booking status."""
    booking_id = data.booking_id

    booking = get_booking(booking_id)
    if not booking:
        return JSONResponse({"error": "Booking not found"}, status_code=404)

    confirm_booking(booking_id)
    logger.info(f"Booking #{booking_id} confirmed via API!")

    return {"status": "confirmed", "booking_id": booking_id}


# ─── REAL-TIME IN-ROOM DINING ENDPOINTS ──────────────────

@app.get("/api/orders/{chat_id}")
async def get_user_orders(chat_id: int):
    """Get active food orders for a user."""
    orders = get_active_food_orders(chat_id)
    return {"status": "success", "orders": orders}

@app.post("/kitchen/update-status")
async def update_order_status(update: OrderUpdate):
    """
    Direct Push Architecture:
    The kitchen calls this to update status, and the server PUSHES
    a notification directly to the Telegram user in real-time.
    """
    if not TELEGRAM_BOT_TOKEN:
        return JSONResponse({"error": "TELEGRAM_BOT_TOKEN not configured"}, status_code=500)

    # 1. Update SQLite real-time database
    row = update_food_order_status(update.order_id, update.status)
    if not row:
        return JSONResponse({"error": "Order not found"}, status_code=404)

    # 2. Build status-specific messages
    status_msg = {
        "PREPARING": "🍳 Your Chef is now preparing your meal!",
        "PLATING": "✨ The kitchen is adding the final touches.",
        "EN_ROUTE": "🛎️ On its way! Your server is heading to your door.",
        "DELIVERED": "✅ Delivered! Enjoy your fantastic meal."
    }.get(update.status, f"Update: {update.status}")

    # 3. PUSH directly to Telegram User
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    message_text = (
        f"🛎 *Live Order Tracker* 🛎\n\n"
        f"Order #{update.order_id} has a new update:\n"
        f"**{status_msg}**"
    )
    
    try:
        await bot.send_message(chat_id=update.chat_id, text=message_text, parse_mode="Markdown")
        logger.info(f"Live update pushed to user {update.chat_id} for order #{update.order_id}")
    except Exception as e:
        logger.error(f"Failed to push message via Telegram: {e}")
        return JSONResponse({"error": f"Failed to push to Telegram: {str(e)}"}, status_code=500)

    return {"status": "success", "message": "Guest notified instantly."}

# ─── GOOGLE SHEETS WEBHOOK ENDPOINT ─────────────────────────

@app.post("/webhook/sheets-edit")
async def sheets_webhook(request: Request):
    """
    Receives HTTP POST requests when a user edits the Google Sheet.
    Used for 2-way sync (Google Sheets -> Local DB)
    """
    try:
        data = await request.json()
        logger.info(f"Received Google Sheets edit payload: {data}")
        
        target_type = data.get("type")  # "booking" or "food_order"
        row_id = data.get("id")
        field = data.get("field")
        value = data.get("value")

        if not target_type or not row_id or not field:
            return JSONResponse({"error": "Missing required fields in payload"}, status_code=400)

        # Map spreadsheet headers to database column names if necessary
        header_map = {
            "ID": "id",
            "Name": "guest_name",
            "Phone": "guest_phone",
            "Room Number": "room_number",
            "Check In": "check_in",
            "Check Out": "check_out",
            "Nights": "nights",
            "Total Price": "total_price",
            "Status": "status",
            "Items": "items"
        }
        
        db_field = header_map.get(field, field.lower().replace(" ", "_"))

        success = False
        if target_type == "booking":
            success = update_booking_field(row_id, db_field, value)
        elif target_type == "food_order":
            success = update_food_order_field(row_id, db_field, value)

        if success:
            logger.info(f"Succesfully synced {target_type} #{row_id} update from Sheets.")
            return {"status": "success", "message": f"{target_type} updated"}
        else:
            return JSONResponse({"error": "Failed to update database"}, status_code=500)

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error processing sheets webhook: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
