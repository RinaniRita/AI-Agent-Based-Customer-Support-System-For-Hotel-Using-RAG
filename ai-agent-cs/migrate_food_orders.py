"""
Migration: Add room_number column to food_orders table.
SQLite does not support dropping/recreating columns easily,
so we do a safe ALTER TABLE ADD COLUMN migration.
"""
import sys, os
sys.path.insert(0, '.')
from backend.database.db_service import get_connection

conn = get_connection()
cursor = conn.cursor()

# Check if room_number already exists
cols = [row[1] for row in cursor.execute("PRAGMA table_info(food_orders)").fetchall()]
print(f"Current food_orders columns: {cols}")

if 'room_number' not in cols:
    print("Migrating: Adding 'room_number' column to food_orders...")
    cursor.execute("ALTER TABLE food_orders ADD COLUMN room_number INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    print("Migration complete!")
else:
    print("room_number column already exists. No migration needed.")

# Verify
cols_after = [row[1] for row in cursor.execute("PRAGMA table_info(food_orders)").fetchall()]
print(f"food_orders columns after migration: {cols_after}")
conn.close()
