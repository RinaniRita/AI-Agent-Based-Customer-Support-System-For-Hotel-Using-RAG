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


def seed_all():
    """Seed room types and 40 physical rooms."""
    conn = get_connection()

    # 1. Seed room types
    for room_type, name, price, max_occ, floor in ROOM_TYPES:
        conn.execute("""
            INSERT OR IGNORE INTO rooms (room_type, display_name, price_per_night, max_occupancy, floor_number)
            VALUES (?, ?, ?, ?, ?)
        """, (room_type, name, price, max_occ, floor))

    # 2. Seed 5 physical rooms per type (e.g., Floor 1 → 101-105)
    for room_type, _, _, _, floor in ROOM_TYPES:
        for i in range(1, 6):
            room_number = floor * 100 + i  # 101, 102, ... 805
            conn.execute("""
                INSERT OR IGNORE INTO physical_rooms (room_number, room_type)
                VALUES (?, ?)
            """, (room_number, room_type))

    conn.commit()
    conn.close()
    print(f"✅ Seeded {len(ROOM_TYPES)} room types and {len(ROOM_TYPES) * 5} physical rooms.")


if __name__ == "__main__":
    print("🏨 Initializing Luxury Hotel database (40 physical rooms)...")
    init_db()
    seed_all()
    print("✅ Database setup complete! File: data/hotel_data.db")
