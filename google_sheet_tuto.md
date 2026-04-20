# 📊 Google Sheets Two-Way Sync Tutorial

This guide explains how to connect your **Luxury Hotel AI System** to **Google Sheets** so that your staff can manage bookings manually while the Telegram bot stays updated in real-time.

---

## 🏗️ How it Works
1.  **Local → Sheet (Push)**: When a guest bookings or order food on Telegram, the Python app sends a POST request to a Google Apps Script Webhook.
2.  **Sheet → Local (Pull)**: When staff edits a cell in Google Sheets, an Apps Script trigger sends a POST request back to your local FastAPI server (via Ngrok).

---

## 🛠️ Step 1: Prepare your Spreadsheet
Ensure your Google Sheet has exactly these 3 tabs with these column headers in **Row 1**:

1.  **`customer_info`** (Room Bookings)
    - Headers: `ID`, `Name`, `Email`, `Phone`, `Room Number`, `Check In`, `Check Out`, `Total Price`, `Status`
2.  **`order_food`** (Kitchen)
    - Headers: `ID`, `Room Number`, `Items`, `Total Price`, `Status`
3.  **`customer_request`** (Front Desk)
    - Headers: `ID`, `room number`, `request`, `Status`

---

## 📜 Step 2: Add the Apps Script (SMART SYNC V2.2)
1.  In your Google Sheet, go to **Extensions** > **Apps Script**.
2.  Delete all existing code and paste the following:

```javascript
/**
 * Apollo Hotel SMART SYNC SCRIPT
 * Version: 2.2 (Synced with Telegram Button Order)
 */

function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var action = data.action;
  var payload = data.data;
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  var sheet;
  var newRow;

  // 1. Identify Target Sheet & Format Data Row to match YOUR headers
  if (action === "upsert_booking") {
    sheet = ss.getSheetByName("customer_info");
    newRow = [
      payload.id, 
      payload.guest_name, 
      payload.guest_email,
      payload.guest_phone, 
      payload.room_number, 
      payload.check_in, 
      payload.check_out, 
      payload.total_price, 
      payload.status
    ];
  } 
  else if (action === "upsert_food") {
    sheet = ss.getSheetByName("order_food");
    newRow = [
      payload.id, 
      payload.room_number, 
      payload.items, 
      payload.total_price, 
      payload.status
    ];
  } 
  else if (action === "upsert_service") {
    sheet = ss.getSheetByName("customer_request");
    newRow = [
      payload.id, 
      payload.room_number, 
      payload.request, 
      payload.status
    ];
  }

  if (!sheet) return ContentService.createTextOutput("Sheet not found: " + action);

  // 2. Search for the existing row by ID (Column A)
  var targetId = String(payload.id);
  var dataRange = sheet.getDataRange();
  var values = dataRange.getValues();
  var rowIndex = -1;

  for (var i = 1; i < values.length; i++) {
    if (String(values[i][0]) === targetId) {
      rowIndex = i + 1;
      break;
    }
  }

  // 3. Update Existing OR Append New
  if (rowIndex !== -1) {
    sheet.getRange(rowIndex, 1, 1, newRow.length).setValues([newRow]);
  } else {
    sheet.appendRow(newRow);
  }

  return ContentService.createTextOutput("Success");
}

function sendEditToBackend(e) {
  if (!e || !e.range) return;
  var sheet = e.source.getActiveSheet();
  var sheetName = sheet.getName().toLowerCase();
  
  // Detect target type based on YOUR tab names
  var targetType = "booking"; 
  if (sheetName.includes("food")) targetType = "food_order";
  else if (sheetName.includes("request")) targetType = "service_request";

  if (e.range.getRow() === 1) return;

  var rowId = sheet.getRange(e.range.getRow(), 1).getValue();
  var headerName = sheet.getRange(1, e.range.getColumn()).getValue();

  var payload = {
    "type": targetType,
    "id": rowId,
    "field": headerName,
    "value": e.value || ""
  };

  try {
    var webhookUrl = "https://nonextrusive-hannah-unprodded.ngrok-free.dev/webhook/sheets-edit";
    UrlFetchApp.fetch(webhookUrl, {
      "method": "post",
      "contentType": "application/json",
      "payload": JSON.stringify(payload)
    });
  } catch (err) {
    Logger.log("Sync Error: " + err);
  }
}
```

---

## ✅ Step 3: Setup Dropdown Sync (Data Validation)
To make your Google Sheet "Status" column work exactly like the Telegram buttons, set up **Data Validation** (Dropdowns) with these exact strings:

### 1. For `order_food` (Matching Kitchen Bot):
*   Select the **Status** column cells.
*   Insert > **Dropdown**.
*   Items (In this order):
    - `RECEIVED`
    - `PREPARING`
    - `EN_ROUTE`
    - `DELIVERED`
    - `CANCELLED`

### 2. For `customer_info` (Matching Booking Bot):
*   Items (In this order):
    - `CONFIRMED`
    - `CHECK_IN`
    - `CHECK_OUT`
    - `CANCELLED`

### 3. For `customer_request` (Matching Service Bot):
*   Items (In this order):
    - `PENDING`
    - `INPROGRESS`
    - `COMPLETE`
    - `CANCELLED`

---

## 🚀 Step 4: Deploy & Authorize
1.  Click **Deploy** > **Manage Deployments**.
2.  Edit the existing deployment (Pencil icon).
3.  Set "Version" to **New version**.
4.  Click **Deploy**.

---

## 📡 Step 5: Start the Tunnel (Ngrok)
If you restart Ngrok, your URL will change! You must update the `webhookUrl` in the Apps Script and the `BACKEND_WEBHOOK_URL` in `.env` every time.

> [!IMPORTANT]
> If you change a status in Google Sheets, the guest will receive an instant Telegram notification just like if you clicked the button in the bot!
