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
