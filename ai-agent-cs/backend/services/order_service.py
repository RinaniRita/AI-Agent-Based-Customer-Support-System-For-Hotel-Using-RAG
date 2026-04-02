import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.database.db_service import get_connection

def get_order_status(order_id: int) -> str:
    """Get the status of an existing food order."""
    conn = get_connection()
    row = conn.execute("SELECT status FROM food_orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    
    if not row:
        return ""
        
    db_status = row["status"].upper().strip()
    if "PREPARING" in db_status:
        return "preparing"
    elif "EN_ROUTE" in db_status or "DELIVERING" in db_status:
        return "delivering"
    elif "DELIVERED" in db_status:
        return "completed"
    elif "CANCELLED" in db_status:
        return "cancelled"
    else:
        return "pending"
