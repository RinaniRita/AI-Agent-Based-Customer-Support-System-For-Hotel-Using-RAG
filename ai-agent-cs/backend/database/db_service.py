import sqlite3
import os
import logging
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from backend.services.sheets_sync import (
    sync_booking_to_sheet, 
    sync_food_order_to_sheet, 
    sync_service_request_to_sheet
)

logger = logging.getLogger(__name__)

# Database file path (relative to project root)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "hotel_data.db")


def get_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize the database with the schema."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_type       TEXT PRIMARY KEY,
            display_name    TEXT NOT NULL,
            price_per_night REAL NOT NULL,
            max_occupancy   INTEGER NOT NULL,
            floor_number    INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS physical_rooms (
            room_number     INTEGER PRIMARY KEY,
            room_type       TEXT NOT NULL,
            FOREIGN KEY (room_type) REFERENCES rooms(room_type)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER NOT NULL,
            room_type       TEXT NOT NULL,
            room_number     INTEGER,
            guest_name      TEXT,
            guest_email     TEXT,
            guest_phone     TEXT,
            check_in        TEXT,
            check_out       TEXT,
            nights          INTEGER,
            total_price     REAL,
            status          TEXT NOT NULL DEFAULT 'PENDING_INFO',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_type) REFERENCES rooms(room_type),
            FOREIGN KEY (room_number) REFERENCES physical_rooms(room_number)
        );

        CREATE TABLE IF NOT EXISTS service_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER NOT NULL,
            room_number     INTEGER, -- Added for multi-room support
            request_type    TEXT NOT NULL,
            details         TEXT,
            status          TEXT NOT NULL DEFAULT 'PENDING',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS food_orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id         INTEGER NOT NULL,
            room_number     INTEGER NOT NULL,
            items           TEXT NOT NULL,
            total_price     REAL NOT NULL DEFAULT 0,
            status          TEXT NOT NULL DEFAULT 'RECEIVED',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS food_menu (
            item_name       TEXT PRIMARY KEY,
            category        TEXT NOT NULL,
            price           REAL NOT NULL,
            stock           INTEGER NOT NULL DEFAULT 0
        );
    """)

    conn.commit()

    # ── Safe migrations ──
    existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(food_orders)").fetchall()]
    if 'room_number' not in existing_cols:
        cursor.execute("ALTER TABLE food_orders ADD COLUMN room_number INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        logger.info("Migration applied: added room_number to food_orders.")
    if 'booking_id' not in existing_cols:
        cursor.execute("ALTER TABLE food_orders ADD COLUMN booking_id INTEGER")
        conn.commit()
        logger.info("Migration applied: added booking_id to food_orders.")

    # Migration for service_requests
    existing_svc_cols = [row[1] for row in cursor.execute("PRAGMA table_info(service_requests)").fetchall()]
    if 'room_number' not in existing_svc_cols:
        cursor.execute("ALTER TABLE service_requests ADD COLUMN room_number INTEGER")
        conn.commit()
        logger.info("Migration applied: added room_number to service_requests.")

    conn.close()
    logger.info("Database initialized successfully.")


# ─── Room Queries ───────────────────────────────────────────

def get_room_info(room_type):
    """Get room details by type."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM rooms WHERE room_type = ?", (room_type,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_available_room_numbers(room_type, check_in, check_out):
    """
    Return a list of AVAILABLE physical room numbers for a given room type and date range.
    A room is unavailable if it has a CONFIRMED or PENDING_PAYMENT booking that overlaps the dates.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT pr.room_number FROM physical_rooms pr
        WHERE pr.room_type = ?
          AND pr.room_number NOT IN (
              SELECT b.room_number FROM bookings b
              WHERE b.room_type = ?
                AND b.room_number IS NOT NULL
                AND b.status IN ('CONFIRMED', 'PENDING_PAYMENT', 'PENDING_GUEST_INFO', 'PAYMENT_RECEIVED', 'CHECK_IN', 'CHECK IN')
                AND b.check_in < ?
                AND b.check_out > ?
          )
        ORDER BY pr.room_number
    """, (room_type, room_type, check_out, check_in)).fetchall()
    conn.close()
    return [r["room_number"] for r in rows]


def check_availability(room_type, check_in, check_out):
    """Check how many rooms of this type are available for the given dates."""
    return len(get_available_room_numbers(room_type, check_in, check_out))


def get_booked_dates_for_type(room_type):
    """
    Return a list of date ranges where ALL 5 rooms of this type are booked (fully sold out).
    Useful for showing the guest which dates are unavailable.
    """
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as cnt FROM physical_rooms WHERE room_type = ?", (room_type,)).fetchone()["cnt"]
    rows = conn.execute("""
        SELECT check_in, check_out, COUNT(*) as booked_count
        FROM bookings
        WHERE room_type = ?
          AND status IN ('CONFIRMED', 'PENDING_PAYMENT', 'PENDING_GUEST_INFO', 'PAYMENT_RECEIVED', 'CHECK_IN', 'CHECK IN')
          AND room_number IS NOT NULL
        GROUP BY check_in, check_out
        HAVING booked_count >= ?
    """, (room_type, total)).fetchall()
    conn.close()
    return [{"check_in": r["check_in"], "check_out": r["check_out"]} for r in rows]


# ─── Booking Queries ────────────────────────────────────────

def create_booking(telegram_id, room_type):
    """Create a new pending booking and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO bookings (telegram_id, room_type, status) VALUES (?, ?, 'PENDING_INFO')",
        (telegram_id, room_type)
    )
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return booking_id


def update_booking_dates(booking_id, check_in, check_out, nights):
    """
    Update the check-in/check-out dates for a booking and assign a specific physical room.
    Returns the assigned room number, or None if no rooms are available.
    """
    conn = get_connection()
    booking = conn.execute("SELECT room_type FROM bookings WHERE id = ?", (booking_id,)).fetchone()
    room_type = booking["room_type"]
    price = conn.execute("SELECT price_per_night FROM rooms WHERE room_type = ?", (room_type,)).fetchone()["price_per_night"]
    total = price * nights

    # Find an available physical room
    available = get_available_room_numbers(room_type, check_in, check_out)
    if not available:
        conn.close()
        return None

    assigned_room = available[0]  # Assign the first available room

    conn.execute("""
        UPDATE bookings
        SET check_in = ?, check_out = ?, nights = ?, total_price = ?,
            room_number = ?, status = 'PENDING_GUEST_INFO'
        WHERE id = ?
    """, (check_in, check_out, nights, total, assigned_room, booking_id))
    conn.commit()
    conn.close()
    return assigned_room


def update_booking_guest_info(booking_id, name, email, phone):
    """Update guest personal information for a booking."""
    conn = get_connection()
    conn.execute("""
        UPDATE bookings SET guest_name = ?, guest_email = ?, guest_phone = ?, status = 'PENDING_PAYMENT'
        WHERE id = ?
    """, (name, email, phone, booking_id))
    conn.commit()
    conn.close()
    try:
        booking = get_booking(booking_id)
        if booking:
            threading.Thread(target=sync_booking_to_sheet, args=(booking,), daemon=True).start()
    except Exception as e:
        logger.error(f"Failed to trigger sync for booking {booking_id}: {e}")


def update_booking_field(booking_id, field, value):
    """Generic function to update a single field in a booking, and sync to Google Sheets."""
    conn = get_connection()
    try:
        # Check if column exists to prevent SQL injection or errors
        cursor = conn.execute(f"PRAGMA table_info(bookings)")
        columns = [row[1] for row in cursor.fetchall()]
        if field not in columns:
            logger.error(f"Invalid field name: {field}")
            return False

        conn.execute(f"UPDATE bookings SET {field} = ? WHERE id = ?", (value, booking_id))
        conn.commit()
        logger.info(f"Updated booking #{booking_id} field '{field}' to '{value}'")
    except Exception as e:
        logger.error(f"Error updating booking field: {e}")
        return False
    finally:
        conn.close()

    # Sync to sheets AFTER connection is closed
    try:
        sync_booking_to_sheet(get_booking(booking_id))
    except Exception as e:
        logger.error(f"Failed to sync booking {booking_id} to sheet: {e}")
        
    return True


def confirm_booking(booking_id):
    """Mark a booking as confirmed (after payment)."""
    conn = get_connection()
    conn.execute("UPDATE bookings SET status = 'CONFIRMED' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    try:
        sync_booking_to_sheet(get_booking(booking_id))
    except Exception as e:
        logger.error(f"Failed to sync booking {booking_id}: {e}")


def get_booking(booking_id):
    """Retrieve a booking by ID."""
    conn = get_connection()
    row = conn.execute("""
        SELECT b.*, r.display_name, r.price_per_night
        FROM bookings b
        JOIN rooms r ON b.room_type = r.room_type
        WHERE b.id = ?
    """, (booking_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_booking_by_room(room_number):
    """Retrieve an active Checked In booking for a given room number."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM bookings WHERE room_number = ? AND status IN ('CHECK_IN', 'CHECK IN')",
        (room_number,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Service Request Queries ────────────────────────────────

def create_service_request(telegram_id, request_type, details="", room_number=None):
    """Create a new service request, linked to a specific room if provided."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO service_requests (telegram_id, request_type, details, room_number) VALUES (?, ?, ?, ?)",
        (telegram_id, request_type, details, room_number)
    )
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Attempt to sync to Google Sheets in a background thread (non-blocking)
    try:
        req_data = get_service_request(req_id)
        if req_data:
            threading.Thread(target=sync_service_request_to_sheet, args=(req_data,), daemon=True).start()
    except Exception as e:
        logger.error(f"Failed to trigger sync for service request {req_id}: {e}")

    return req_id


def get_service_request(req_id):
    """Fetch service request details."""
    conn = get_connection()
    row = conn.execute("""
        SELECT sr.*
        FROM service_requests sr
        WHERE sr.id = ?
    """, (req_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_service_request_status(req_id, new_status):
    """Internal update of service status."""
    conn = get_connection()
    conn.execute("UPDATE service_requests SET status = ? WHERE id = ?", (new_status, req_id))
    conn.commit()
    conn.close()
    
    # Sync update to sheet in background
    req = get_service_request(req_id)
    if req:
        threading.Thread(target=sync_service_request_to_sheet, args=(req,), daemon=True).start()
    return req


def update_service_request_field(req_id, field, value):
    """Generic function to update a single field in a service request from webhook."""
    conn = get_connection()
    try:
        # Map sheet headers to DB columns if necessary
        header_map = {
            "ID": "id",
            "Room Number": "room_number",
            "room number": "room_number",
            "Request": "details",
            "request": "details",
            "Status": "status"
        }
        db_field = header_map.get(field, field.lower())
        
        # Valid columns check
        cursor = conn.execute("PRAGMA table_info(service_requests)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if db_field == "room_number":
            logger.warning("Attempted to update readonly field room_number")
            return False

        if db_field not in columns:
            logger.error(f"Invalid field name for service_requests: {db_field}")
            return False

        conn.execute(f"UPDATE service_requests SET {db_field} = ? WHERE id = ?", (value, req_id))
        conn.commit()
        logger.info(f"Updated service request #{req_id} field '{db_field}' to '{value}'")
    except Exception as e:
        logger.error(f"Error updating service request field: {e}")
        return False
    finally:
        conn.close()

    # Sync to sheets AFTER connection is closed (Background)
    try:
        req_data = get_service_request(req_id)
        if req_data:
            threading.Thread(target=sync_service_request_to_sheet, args=(req_data,), daemon=True).start()
    except Exception as e:
        logger.error(f"Failed to trigger sync for service request {req_id}: {e}")

    return True


# ─── User-Based Access Control ──────────────────────────────

def get_booking_by_user(user_id: int):
    """Fetch the most relevant active booking for a Telegram user — CHECK_IN first, then latest."""
    conn = get_connection()
    row = conn.execute("""
        SELECT b.*, r.display_name, r.price_per_night
        FROM bookings b
        JOIN rooms r ON b.room_type = r.room_type
        WHERE b.telegram_id = ?
          AND b.status NOT IN ('CANCELLED', 'CHECK_OUT', 'CHECK OUT', 'PENDING_INFO', 'PENDING_GUEST_INFO')
        ORDER BY
            CASE
                WHEN UPPER(b.status) IN ('CHECK_IN', 'CHECK IN') THEN 0
                WHEN UPPER(b.status) = 'CONFIRMED' THEN 1
                WHEN UPPER(b.status) IN ('PAYMENT_RECEIVED', 'PAYMENT RECEIVED') THEN 2
                ELSE 3
            END ASC,
            b.created_at DESC
        LIMIT 1
    """, (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_active_bookings_by_user(user_id: int):
    """Fetch all active bookings for a Telegram user (excluding cancelled or checked out)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT b.*, r.display_name, r.price_per_night
        FROM bookings b
        JOIN rooms r ON b.room_type = r.room_type
        WHERE b.telegram_id = ?
          AND b.status NOT IN ('CANCELLED', 'CHECK_OUT', 'CHECK OUT')
          AND b.room_number IS NOT NULL
        ORDER BY b.created_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def validate_user_booking(user_id: int) -> bool:
    """Returns True if user has any active booking."""
    return get_booking_by_user(user_id) is not None


def can_order_food(user_id: int) -> bool:
    """Returns True only if the user's active booking has status CHECK_IN."""
    booking = get_booking_by_user(user_id)
    if not booking:
        return False
    status = booking["status"].upper().strip()
    return status in ("CHECK_IN", "CHECK IN")


# ─── Food Order Queries ─────────────────────────────────────

def create_food_order(chat_id, room_number, items_json, total_price, booking_id=None):
    """Create a food order linked to a booking and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO food_orders (chat_id, room_number, items, total_price, status, booking_id) VALUES (?, ?, ?, ?, 'RECEIVED', ?)",
        (chat_id, room_number, items_json, total_price, booking_id)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    try:
        order = get_food_order(order_id)
        if order:
            threading.Thread(target=sync_food_order_to_sheet, args=(order,), daemon=True).start()
    except Exception as e:
        logger.error(f"Failed to trigger sync for food order {order_id}: {e}")
    return order_id


def update_food_order_status(order_id, new_status):
    """Update the status of a food order. Returns the order row or None."""
    conn = get_connection()
    conn.execute(
        "UPDATE food_orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, order_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM food_orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    
    res = dict(row) if row else None
    if res:
        try:
            threading.Thread(target=sync_food_order_to_sheet, args=(res,), daemon=True).start()
        except Exception as e:
            logger.error(f"Failed to trigger sync for food order {order_id}: {e}")
    return res


def get_food_order(order_id):
    """Get a food order by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM food_orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_food_orders(chat_id):
    """Get all active (non-delivered) food orders for a chat."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM food_orders WHERE chat_id = ? AND status != 'DELIVERED' ORDER BY created_at DESC",
        (chat_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_food_order_field(order_id, field, value):
    """Generic function to update a single field in a food order."""
    conn = get_connection()
    try:
        cursor = conn.execute(f"PRAGMA table_info(food_orders)")
        columns = [row[1] for row in cursor.fetchall()]
        if field not in columns:
            logger.error(f"Invalid field name: {field}")
            return False

        conn.execute(f"UPDATE food_orders SET {field} = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (value, order_id))
        conn.commit()
        logger.info(f"Updated food order #{order_id} field '{field}' to '{value}'")
    except Exception as e:
        logger.error(f"Error updating food order field: {e}")
        return False
    finally:
        conn.close()

    # Sync to sheets AFTER connection is closed (Background)
    try:
        order = get_food_order(order_id)
        if order:
            threading.Thread(target=sync_food_order_to_sheet, args=(order,), daemon=True).start()
    except Exception as e:
        logger.error(f"Failed to trigger sync for food order {order_id} to sheet: {e}")

    return True

