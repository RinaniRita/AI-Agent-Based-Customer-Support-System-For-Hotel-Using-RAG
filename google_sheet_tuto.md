# 📊 Google Sheets Two-Way Sync Tutorial

This guide explains how to connect your **Luxury Hotel AI System** to **Google Sheets** so that your staff can manage bookings manually while the Telegram bot stays updated in real-time.

---

## 🏗️ How it Works
1.  **Local → Sheet (Push)**: When a guest books on Telegram, the Python app sends a POST request to a Google Apps Script Webhook.
2.  **Sheet → Local (Pull)**: When staff edits a cell in Google Sheets, an Apps Script trigger sends a POST request back to your local FastAPI server (via Ngrok).

---

## 🛠️ Step 1: Prepare your Spreadsheet
1.  Create a new Google Sheet.
2.  Rename the first tab to `Customer_Orders`.
3.  Add these headers in the **first row (A1 to J1)**:
    - `ID`, `Name`, `Phone`, `Room Number`, `Check In`, `Check Out`, `Nights`, `Total Price`, `Status`, `Telegram ID`
4.  Create a second tab named `Food_Orders`.
5.  Add these headers in the **first row (A1 to G1)**:
    - `ID`, `Room Number`, `Items`, `Total Price`, `Status`, `Booking ID`, `Chat ID`

---

## 📜 Step 2: Add the Apps Script
1.  In your Google Sheet, go to **Extensions** > **Apps Script**.
2.  Delete all existing code and paste the following:

```javascript
function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Customer_Orders");
  var foodSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Food_Orders");
  var data = JSON.parse(e.postData.contents);
  
  if (data.type === "booking") {
    sheet.appendRow([data.id, data.guest_name, data.guest_phone, data.room_number, data.check_in, data.check_out, data.nights, data.total_price, data.status, data.telegram_id]);
  } else if (data.type === "food_order") {
    foodSheet.appendRow([data.id, data.room_number, data.items, data.total_price, data.status, data.booking_id, data.chat_id]);
  }
  
  return ContentService.createTextOutput("Success");
}

function sendEditToBackend(e) {
  if (!e || !e.range) return;
  
  var sheetName = e.source.getActiveSheet().getName();
  var row = e.range.getRow();
  var col = e.range.getColumn();
  if (row === 1) return; // Ignore header edits

  var rowId = e.source.getActiveSheet().getRange(row, 1).getValue();
  var headerName = e.source.getActiveSheet().getRange(1, col).getValue();
  var newValue = e.value || "";

  var payload = {
    "type": sheetName.toLowerCase().includes("food") ? "food_order" : "booking",
    "id": rowId,
    "field": headerName,
    "value": newValue
  };

  // CHANGE THIS TO YOUR NGROK URL
  var webhookUrl = "https://YOUR_NGROK_URL_HERE.ngrok-free.app/webhook/sheets-edit";

  UrlFetchApp.fetch(webhookUrl, {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload)
  });
}
```

---

## 🚀 Step 3: Deploy & Authorize
1.  Click **Deploy** > **New Deployment**.
2.  Select **Web App**.
3.  Set "Who has access" to **Anyone**.
4.  Copy the **Web App URL** (e.g., `https://script.google.com/macros/s/.../exec`).
5.  **Paste this URL** into your local `.env` file under `GOOGLE_SHEETS_WEBHOOK_URL`.

---

## ⏰ Step 4: Set the "On Edit" Trigger
This step allows the Sheet to talk back to your computer.
1.  On the left side of the Apps Script screen, click the **⏰ Triggers** icon (Clock).
2.  Click **+ Add Trigger**.
3.  Choose `sendEditToBackend`.
4.  Event Source: `From spreadsheet`.
5.  Event type: `On edit`.
6.  Click **Save**.
7.  **IMPORTANT**: A popup will appear. Click your account > **Advanced** > **Go to Project (unsafe)** > **Allow**.

---

## 📡 Step 5: Start the Tunnel (Ngrok)
Since Google cannot "see" your laptop, you must open a tunnel:
1.  Run `ngrok http 8000`.
2.  Copy the `https://...ngrok-free.app` URL.
3.  Go back to the Apps Script code (Step 2) and update the `webhookUrl` variable with your new Ngrok link.
4.  Save the code (💾).

---

## ✅ Step 6: Test it!
1.  Start your servers: `python start_api_server.py` and `python start_telegram_bot.py`.
2.  Book a room on Telegram. The data should appear in your Google Sheet instantly.
3.  Manually change the **Status** of that row in Google Sheets to `CHECK_IN`.
4.  The Telegram bot will instantly send a "Welcome!" message to the guest!

> [!CAUTION]
> If you restart Ngrok, your URL will change! You must update the URL in your Apps Script code every time you get a new Ngrok link.
