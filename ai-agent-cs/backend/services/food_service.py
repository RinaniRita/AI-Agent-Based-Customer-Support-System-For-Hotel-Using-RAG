import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.database.db_service import get_connection

def check_food_inventory(item_name: str) -> bool:
    """Check if a food item is in stock (stock > 0)."""
    conn = get_connection()
    row = conn.execute("SELECT stock FROM food_menu WHERE LOWER(item_name) = ?", (item_name.lower(),)).fetchone()
    conn.close()
    if row and row["stock"] > 0:
        return True
    return False

def suggest_alternative_food(item_name: str) -> list[str]:
    """Find alternative foods in the same category with stock > 0. If none, return popular items."""
    conn = get_connection()
    
    # Get category of requested item
    row = conn.execute("SELECT category FROM food_menu WHERE LOWER(item_name) = ?", (item_name.lower(),)).fetchone()
    
    if row:
        category = row["category"]
        # Same category in stock
        alts = conn.execute(
            "SELECT item_name FROM food_menu WHERE category = ? AND LOWER(item_name) != ? AND stock > 0 LIMIT 3", 
            (category, item_name.lower())
        ).fetchall()
        
        if alts:
            conn.close()
            return [a["item_name"] for a in alts]
            
    # Fallback: popular items across all categories
    alts = conn.execute("SELECT item_name FROM food_menu WHERE stock > 0 ORDER BY stock DESC LIMIT 3").fetchall()
    conn.close()
    return [a["item_name"] for a in alts]
