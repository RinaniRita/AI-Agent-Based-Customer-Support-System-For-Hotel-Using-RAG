"""
Setup script to initialize the hotel database with 40 physical rooms.
Run from project root: python -m backend.database.setup_db

Room numbering (sorted by price, lowest → highest):
  Floor 1 → Standard Double      (€127)  → 101-105
  Floor 2 → Comfort Room         (€142)  → 201-205
  Floor 3 → Superior Room        (€168)  → 301-305
  Floor 4 → Junior Suite         (€175)  → 401-405
  Floor 5 → Standard + Extra Bed (€183)  → 501-505
  Floor 6 → Superior Balcony     (€235)  → 601-605
  Floor 7 → Superior Panoramic   (€235)  → 701-705
  Floor 8 → Superior Suite       (€235)  → 801-805
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.database.db_service import get_connection, init_db

# (room_type, display_name, price, max_occupancy, floor)
# Sorted by price ascending, then alphabetically for same-price tiers
ROOM_TYPES = [
    ("standard",        "Standard Double/Twin Room",           127, 2, 1),
    ("comfort",         "Comfort Double/Twin Room",            142, 2, 2),
    ("superior",        "Superior Room",                       168, 2, 3),
    ("junior_suite",    "Junior Suite",                        175, 4, 4),
    ("standard_extra",  "Standard Room + Extra Bed",           183, 3, 5),
    ("sup_balcony",     "Superior Room with Balcony",          235, 2, 6),
    ("sup_panoramic",   "Superior Panoramic Window + Balcony", 235, 2, 7),
    ("sup_suite",       "Superior Suite",                      235, 4, 8),
]


import json

def seed_all():
    """Seed room types, physical rooms, and food menu from JSON mock data."""
    conn = get_connection()

    # Load Rooms
    rooms_path = os.path.join(os.path.dirname(__file__), "..", "..", "static_data", "rooms", "rooms.json")
    with open(rooms_path, "r", encoding="utf-8") as f:
        rooms_data = json.load(f)

    # 1. Seed room types
    for r in rooms_data:
        conn.execute("""
            INSERT OR IGNORE INTO rooms (room_type, display_name, price_per_night, max_occupancy, floor_number)
            VALUES (?, ?, ?, ?, ?)
        """, (r["room_type"], r["display_name"], r["price_per_night"], r["max_occupancy"], r["floor_number"]))

    # 2. Seed 5 physical rooms per type (e.g., Floor 1 → 101-105)
    for r in rooms_data:
        for i in range(1, 6):
            room_number = r["floor_number"] * 100 + i
            conn.execute("""
                INSERT OR IGNORE INTO physical_rooms (room_number, room_type)
                VALUES (?, ?)
            """, (room_number, r["room_type"]))

    # 3. Seed Food Inventory
    food_path = os.path.join(os.path.dirname(__file__), "..", "..", "static_data", "food", "food_inventory.json")
    with open(food_path, "r", encoding="utf-8") as f:
        food_data = json.load(f)

    for item in food_data:
        conn.execute("""
            INSERT OR IGNORE INTO food_menu (item_name, category, price, stock)
            VALUES (?, ?, ?, ?)
        """, (item["item_name"], item["category"], item["price"], item["stock"]))

    # 4. Seed a dummy active guest in Room 101
    conn.execute("""
        INSERT OR IGNORE INTO bookings 
        (telegram_id, room_type, room_number, guest_name, guest_email, guest_phone, check_in, check_out, nights, total_price, status)
        VALUES (?, ?, ?, ?, ?, ?, date('now'), date('now', '+3 days'), ?, ?, ?)
    """, (
        123456789, "standard", 101, "Jane Doe", "jane@example.com", "+1234567890", 3, 381.0, "CONFIRMED"
    ))

    conn.commit()
    conn.close()
    print(f"✅ Seeded {len(rooms_data)} room types, {len(rooms_data) * 5} physical rooms, {len(food_data)} food items.")


if __name__ == "__main__":
    print("🏨 Initializing Luxury Hotel database (40 physical rooms)...")
    init_db()
    seed_all()
    print("✅ Database setup complete! File: data/hotel_data.db")
