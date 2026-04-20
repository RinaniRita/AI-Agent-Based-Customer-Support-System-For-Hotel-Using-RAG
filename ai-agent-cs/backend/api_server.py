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

# Import Database service
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.database.db_service import (
    init_db, create_booking, update_booking_dates,
    update_booking_guest_info, get_booking, get_room_info,
    check_availability, get_available_room_numbers,
    create_food_order, get_active_food_orders, get_active_booking_by_room,
    update_service_request_field, get_service_request, update_booking_field, update_food_order_field,
    get_food_order, confirm_booking, update_food_order_status, get_connection
)
from backend.services.food_service import check_food_inventory, suggest_alternative_food
from backend.services.room_service import check_room_availability, get_room_status
from backend.services.order_service import get_order_status
from backend.config import TELEGRAM_BOT_TOKEN

logger = logging.getLogger(__name__)

app = FastAPI(title="Luxury Hotel API")

# Enable CORS for GitHub pages frontend!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*", "ngrok-skip-browser-warning"],
)

@app.on_event("startup")
async def startup():
    """Ensure database is initialized on server start."""
    init_db()
    logger.info("FastAPI JSON API server started.")

# Serve the frontend statically so everything is bundled in ONE container!
from fastapi.staticfiles import StaticFiles
import os

frontend_path = os.path.join(os.path.dirname(__file__), "..", "github_pages_frontend")
if os.path.exists(frontend_path):
    app.mount("/frontend", StaticFiles(directory=frontend_path), name="frontend")
    logger.info(f"Serving frontend from {frontend_path} at /frontend")
else:
    logger.warning(f"Frontend directory not found at {frontend_path}")

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
        "RECEIVED": "📥 Your order has been received by the kitchen.",
        "PREPARING": "🍳 Your Chef is now preparing your meal!",
        "PLATING": "✨ The kitchen is adding the final touches (Plating).",
        "EN_ROUTE": "🛎️ On its way! Your server is heading to your door.",
        "DELIVERED": "✅ Delivered! Enjoy your fantastic meal.",
        "CANCELLED": "❌ Your order has been cancelled."
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

# ─── ROOM / FOOD / ORDER STATUS ROUTES ───────────────────────

@app.get("/api/room/{room_number}/availability")
async def api_check_room_availability(room_number: int):
    """Check if a physical room is available right now."""
    available = check_room_availability(room_number)
    return {
        "room_number": room_number,
        "available": available,
        "message": f"Room {room_number} is {'available' if available else 'currently booked'}."
    }

@app.get("/api/room/{room_number}/status")
async def api_get_room_status(room_number: int):
    """Get the live status of a physical room."""
    status = get_room_status(room_number)
    status_labels = {
        "available": "Room is currently available.",
        "booked": "Room is currently booked.",
        "check_in": "Room is currently occupied (checked in).",
        "check_out": "Room is being prepared after check-out.",
    }
    return {
        "room_number": room_number,
        "status": status,
        "message": status_labels.get(status, f"Room status: {status}")
    }

@app.get("/api/food/inventory")
async def api_get_food_inventory():
    """Return the full food inventory from the database."""
    conn = get_connection()
    rows = conn.execute("SELECT item_name, category, price, stock FROM food_menu ORDER BY category").fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}

@app.get("/api/food/{item_name}/availability")
async def api_check_food_availability(item_name: str):
    """Check if a specific food item is in stock."""
    in_stock = check_food_inventory(item_name)
    alternatives = []
    if not in_stock:
        alternatives = suggest_alternative_food(item_name)
    return {
        "item_name": item_name,
        "in_stock": in_stock,
        "alternatives": alternatives
    }

@app.get("/api/order/{order_id}/status")
async def api_get_order_status(order_id: int):
    """Return the current status of a food order."""
    status = get_order_status(order_id)
    if not status:
        return JSONResponse({"error": "Order not found"}, status_code=404)
    status_labels = {
        "pending": "Your order is pending.",
        "preparing": "Your order is being prepared.",
        "delivering": "Your order is on the way.",
        "completed": "Your order has been delivered.",
        "cancelled": "Your order has been cancelled.",
    }
    return {
        "order_id": order_id,
        "status": status,
        "message": status_labels.get(status, f"Order status: {status}")
    }

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

        if not target_type or row_id is None or not field:
            return JSONResponse({"error": "Missing required fields in payload"}, status_code=400)
            
        # Ensure ID is an integer for database matching
        try:
            row_id = int(row_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid non-integer ID received: {row_id}")
            return JSONResponse({"error": "ID must be an integer"}, status_code=400)

        # Map spreadsheet headers to database column names if necessary
        header_map = {
            "ID": "id",
            "Name": "guest_name",
            "Email": "guest_email",
            "Phone": "guest_phone",
            "Room Number": "room_number",
            "Check In": "check_in",
            "Check Out": "check_out",
            "Nights": "nights",
            "Total Price": "total_price",
            "Status": "status",
            "Items": "items"
        }
        
        db_field = header_map.get(field) or field.lower().replace(" ", "_")
        
        # Normalize status values (e.g., "check in" -> "CHECK_IN")
        norm_value = value
        if db_field == "status" and value:
            norm_value = value.upper().strip().replace(" ", "_")
            logger.info(f"Normalized status '{value}' to '{norm_value}'")

        success = False
        if target_type == "booking":
            success = update_booking_field(row_id, db_field, norm_value)
        elif target_type == "food_order":
            success = update_food_order_field(row_id, db_field, norm_value)
        elif target_type == "service_request":
            success = update_service_request_field(row_id, db_field, norm_value)

        if success:
            logger.info(f"Succesfully synced {target_type} #{row_id} update from Sheets.")
            
            # --- REAL-TIME TELEGRAM PUSH NOTIFICATION LOGIC ---
            if db_field == "status" and TELEGRAM_BOT_TOKEN:
                try:
                    bot = Bot(token=TELEGRAM_BOT_TOKEN)
                    msg_value = str(value).upper().strip()
                    chat_id = None
                    text = None
                    
                    if target_type == "booking":
                        booking = get_booking(row_id)
                        if booking and booking.get("telegram_id"):
                            chat_id = booking["telegram_id"]
                            b_map = {
                                "CHECK IN": "🛎️ *Welcome to Luxury Hotel!*\nYou have successfully Checked In to your room. Enjoy your stay!",
                                "CHECK_IN": "🛎️ *Welcome to Luxury Hotel!*\nYou have successfully Checked In to your room. Enjoy your stay!",
                                "CHECK OUT": "👋 *Thank you for staying with us!*\nYour Check Out is complete. Have a safe journey!",
                                "CHECK_OUT": "👋 *Thank you for staying with us!*\nYour Check Out is complete. Have a safe journey!",
                                "CANCELLED": "❌ *Booking Cancelled*\nYour room booking has been successfully cancelled. We hope to see you another time.",
                                "PAYMENT_RECEIVED": "✅ *Payment Confirmed*\nWe have received your room payment securely. Thank you!",
                                "PAYMENT RECEIVED": "✅ *Payment Confirmed*\nWe have received your room payment securely. Thank you!"
                            }
                            text = b_map.get(msg_value)
                            
                    elif target_type == "food_order":
                        order = get_food_order(row_id)
                        if order and order.get("chat_id"):
                            chat_id = order["chat_id"]
                            f_map = {
                                "RECEIVED": "📥 *Order Received*\nYour order has been received by the kitchen.",
                                "PREPARING": "🍳 *Chef is Preparing*\nYour Chef is now preparing your delicious meal!",
                                "PLATING": "✨ *Plating in Progress*\nThe kitchen is adding the final touches to your order.",
                                "EN_ROUTE": "🛎️ *Order En Route*\nYour server is heading to your room now!",
                                "DELIVERED": "✅ *Order Delivered!*\nEnjoy your fantastic meal.",
                                "CANCELLED": "❌ *Order Cancelled*\nYour food order has been cancelled.",
                                "PAYMENT_RECEIVED": "✅ *Payment Confirmed*\nWe have received your in-room dining payment!",
                                "PAYMENT RECEIVED": "✅ *Payment Confirmed*\nWe have received your in-room dining payment!"
                            }
                            text = f_map.get(msg_value)

                    elif target_type == "service_request":
                        service = get_service_request(row_id)
                        if service and service.get("telegram_id"):
                            chat_id = service["telegram_id"]
                            # Define custom messages based on the new status labels
                            status_messages = {
                                "COMPLETE": "✅ *Request Completed*\n\nYour recent service request has been completed. We hope you are satisfied with our service! Thank you.",
                                "INPROGRESS": "🛠️ *Staff is on the Way*\n\nGreat news! A staff member is currently handling your request. It will be fulfilled shortly.",
                                "CANCELLED": "❌ *Request Cancelled*\n\nYour service request has been cancelled by the front desk. If you believe this is an error, please contact us."
                            }
                            text = status_messages.get(msg_value, f"🔔 *Update:* Your service request status is now: *{value}*")
                            
                    if text and chat_id:
                        await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                        logger.info(f"Pushed live Telegram notification to {chat_id} for Status: {msg_value}")
                except Exception as notify_e:
                    logger.error(f"Failed to push Telegram notification: {notify_e}")
            # --- END PUSH LOGIC ---

            return {"status": "success", "message": f"{target_type} updated"}
        else:
            return JSONResponse({"error": "Failed to update database"}, status_code=500)

        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error processing sheets webhook: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)
