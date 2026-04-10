import os
import json
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# The Web App URL you get after deploying the Google Apps Script
SHEETS_WEBHOOK_URL = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")

CUSTOMER_SHEET_ID = os.getenv("CUSTOMER_SHEET_ID")
FOOD_SHEET_ID = os.getenv("FOOD_SHEET_ID")

def sync_booking_to_sheet(booking_data):
    """
    Sends booking data to the Google Sheets Webhook to insert/update the Customer Sheet.
    booking_data should be a dict matching the database row.
    """
    if not SHEETS_WEBHOOK_URL or not CUSTOMER_SHEET_ID:
        logger.warning("Google Sheets sync skipped: Webhook URL or Customer Sheet ID not set.")
        return

    try:
        payload = {
            "action": "upsert_booking",
            "sheet_id": CUSTOMER_SHEET_ID,
            "data": booking_data
        }
        response = requests.post(SHEETS_WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully synced booking {booking_data.get('id')} to Google Sheets.")
    except Exception as e:
        logger.error(f"Failed to sync booking to Google Sheets: {e}")

def sync_food_order_to_sheet(order_data):
    """
    Sends food order data to the Google Sheets Webhook to insert/update the Food Sheet.
    Items are formatted as a clean readable string: "Tuna Tartare €24, Moët & Chandon €55"
    """
    if not SHEETS_WEBHOOK_URL or not FOOD_SHEET_ID:
        logger.warning("Google Sheets sync skipped: Webhook URL or Food Sheet ID not set.")
        return

    try:
        # Format items from raw JSON to a clean, human-readable string
        items_raw = order_data.get("items", "[]")
        try:
            items_list = json.loads(items_raw) if isinstance(items_raw, str) else items_raw
            items_formatted = ", ".join(
                f"{item.get('name', 'Unknown')} €{item.get('price', 0)}"
                for item in items_list
            )
        except (json.JSONDecodeError, TypeError):
            items_formatted = str(items_raw)

        # Build a clean copy of order_data with formatted items
        payload_data = {**order_data, "items": items_formatted}

        payload = {
            "action": "upsert_food",
            "sheet_id": FOOD_SHEET_ID,
            "data": payload_data
        }
        response = requests.post(SHEETS_WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully synced food order {order_data.get('id')} to Google Sheets.")
    except Exception as e:
        logger.error(f"Failed to sync food order to Google Sheets: {e}")

def sync_service_request_to_sheet(request_data):
    """
    Sends service request data to the Google Sheets Webhook.
    request_data should include 'id', 'room_number', and 'request' (details).
    """
    if not SHEETS_WEBHOOK_URL or not CUSTOMER_SHEET_ID:
        logger.warning("Google Sheets sync skipped: Webhook URL or Sheet ID not set.")
        return

    try:
        # Prepare a clean map for the sheet (A: ID, B: Room Number, C: Request, D: Status)
        req_type = request_data.get("request_type", "Request")
        details = request_data.get("details", "")
        # Format as "Type: Details" or just "Type" if details is generic
        full_request = f"{req_type}: {details}" if details and details != "Requested via Telegram" else req_type

        payload_data = {
            "id": request_data.get("id"),
            "room_number": request_data.get("room_number"),
            "request": full_request,
            "status": request_data.get("status", "PENDING")
        }

        payload = {
            "action": "upsert_service",
            "sheet_id": CUSTOMER_SHEET_ID,
            "data": payload_data
        }
        response = requests.post(SHEETS_WEBHOOK_URL, json=payload, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully synced service request {request_data.get('id')} to Google Sheets.")
    except Exception as e:
        logger.error(f"Failed to sync service request to Google Sheets: {e}")

