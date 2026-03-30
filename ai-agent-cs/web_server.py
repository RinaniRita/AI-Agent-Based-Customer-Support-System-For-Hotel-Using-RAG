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

# Import database service
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.database.db_service import get_booking, confirm_booking, init_db

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
