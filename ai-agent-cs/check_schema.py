import sys, os
sys.path.insert(0, '.')
from backend.database.db_service import get_connection, init_db

init_db()  # ensure tables exist
conn = get_connection()

for tbl in ['food_orders', 'bookings', 'rooms', 'physical_rooms']:
    schema = conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{tbl}'").fetchone()
    print(f"\n=== {tbl} ===")
    if schema:
        print(schema[0])
    else:
        print("TABLE NOT FOUND IN DB FILE")

conn.close()
