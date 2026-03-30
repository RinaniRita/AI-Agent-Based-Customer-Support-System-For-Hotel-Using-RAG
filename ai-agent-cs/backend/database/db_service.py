import sqlite3
import os
import logging

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
            request_type    TEXT NOT NULL,
            details         TEXT,
            status          TEXT NOT NULL DEFAULT 'PENDING',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
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
                AND b.status IN ('CONFIRMED', 'PENDING_PAYMENT', 'PENDING_GUEST_INFO')
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
          AND status IN ('CONFIRMED', 'PENDING_PAYMENT', 'PENDING_GUEST_INFO')
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


def confirm_booking(booking_id):
    """Mark a booking as confirmed (after payment)."""
    conn = get_connection()
    conn.execute("UPDATE bookings SET status = 'CONFIRMED' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()


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


# ─── Service Request Queries ────────────────────────────────

def create_service_request(telegram_id, request_type, details=""):
    """Create a new service request and return its ID."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO service_requests (telegram_id, request_type, details) VALUES (?, ?, ?)",
        (telegram_id, request_type, details)
    )
    req_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return req_id
