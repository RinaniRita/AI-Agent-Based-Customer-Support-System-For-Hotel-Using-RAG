import sqlite3
import os
import sys

# Add the project root to sys.path to access backend modules if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "hotel_data.db")

def get_connection():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file not found at {DB_PATH}")
        return None
    return sqlite3.connect(DB_PATH)

def clean_database():
    conn = get_connection()
    if not conn:
        return

    print("🧹 Starting Database Cleanup...")
    cursor = conn.cursor()

    try:
        # 1. Clear User-Generated Data
        print("🗑️  Clearing bookings...")
        cursor.execute("DELETE FROM bookings")
        
        print("🗑️  Clearing food orders...")
        cursor.execute("DELETE FROM food_orders")
        
        print("🗑️  Clearing service requests...")
        cursor.execute("DELETE FROM service_requests")

        # 2. Reset Sequential IDs (Auto-increment counters)
        print("🔄 Resetting ID counters...")
        # tables updated: bookings, food_orders, service_requests
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('bookings', 'food_orders', 'service_requests')")

        conn.commit()
        print("\n✅ Database cleaned successfully!")
        print("   - All bookings removed.")
        print("   - All food orders removed.")
        print("   - All service requests removed.")
        print("   - All ID counters reset to 1.")
        print("\n🏨 Master data (Rooms & Food Menu) was PRESERVED.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error during cleanup: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("⚠️  WARNING: This will permanently delete all guest bookings, food orders, and service requests.")
    confirm = input("Are you sure you want to proceed? (y/n): ").lower()
    
    if confirm == 'y':
        clean_database()
    else:
        print("❌ Cleanup cancelled.")
