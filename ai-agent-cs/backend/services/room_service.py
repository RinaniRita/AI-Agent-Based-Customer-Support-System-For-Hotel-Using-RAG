import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.database.db_service import get_connection

def check_room_availability(room_number: int) -> bool:
    """Check if the physical room is available right now."""
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM bookings 
        WHERE room_number = ? 
          AND status != 'CANCELLED'
          AND check_in <= date('now') 
          AND check_out >= date('now')
    """, (room_number,)).fetchone()
    conn.close()
    return row is None  # True if available, False if booked

def get_room_status(room_number: int) -> str:
    """Return the exact string status of the room ('available', 'booked', 'check_in', 'check_out')."""
    conn = get_connection()
    row = conn.execute("""
        SELECT status FROM bookings 
        WHERE room_number = ? 
          AND status != 'CANCELLED'
          AND check_in <= date('now') 
          AND check_out >= date('now')
    """, (room_number,)).fetchone()
    conn.close()
    
    if not row:
        return "available"
        
    db_status = row["status"].upper().strip()
    if db_status == "CHECK IN" or db_status == "CHECK_IN":
        return "check_in"
    elif db_status == "CHECK OUT" or db_status == "CHECK_OUT":
        return "check_out"
    else:
        # Default fallback if it's reserved but not explicitly checked in
        return "booked"
