# AI-Agent-Based-Hotel-Management-System (Pro)

## 🏨 Introduction

This is a production-ready, professional AI agent framework designed to manage hotel operations through a unified Telegram interface. It combines **Autonomous AI Agents**, **Retrieval-Augmented Generation (RAG)**, and a **Physical Inventory Engine** to provide guests with a seamless, context-aware experience while ensuring 100% data isolation and security.

## 🚀 Key Features

- **🔐 User-Based Access Control**: All bookings and food orders are strictly isolated by Telegram ID. Guests can only view their own reservations.
- **🛡️ "Check-In" Security Policy**: Room service (Food Ordering) is strictly limited to guests who are physically checked into the hotel.
- **🤖 Tool-Calling AI Agent**: Uses Ollama to intelligently classify intents and execute real-time database lookups (Availability, Status, Menu).
- **📊 Real-Time Bi-Directional Sync**: Instant synchronization between the local SQLite database and Google Sheets.
- **🥘 Precision Inventory**: Tracks 40 physical rooms and a real-time food menu with automatic stock subtraction.

---

## 🏗️ Project Structure

The project follows a modular, professional Python architecture, isolating logic into specialized layers:

```text
ai-agent-cs/
├── backend/
│   ├── api_server.py        # FastAPI API (Static Frontend Webhook)
│   ├── bot_server.py        # Telegram Bot Entry Point & State Machine
│   ├── config.py            # Central Configuration & Environment Loading
│   ├── agent/               # AI Intel: Logic, Prompts, and Intent Routers
│   ├── database/            # Data Layer: Seeding, Migrations, and SQL logic
│   ├── data_scripts/        # KB Ingestion: FAISS Vector Store build scripts
│   └── services/            # Business Logic: Room, Food, User, and Sheets logic
├── data/
│   ├── knowledge_base/      # Official Hotel Markdown Documentation
│   ├── vector_store/        # FAISS Index & Embeddings
│   └── hotel_data.db        # Live SQLite Production Database
├── frontend/                # Glassmorphism Static Web UI
└── README.md
```

---

## ⚙️ Setup & Startup

### 1. Requirements
- Python 3.9+
- Ollama (running locally)
- Ngrok (for Google Sheets/GitHub Pages tunnels)

### 2. Initialization
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Seed the 40 physical rooms
python -m backend.database.setup_db

# 3. Ingest the Knowledge Base (RAG)
python -m backend.data_scripts.ingest_kb
```

### 3. Execution (Independent Service Startup)
For the most stable experience, you should run the API and Bot in two separate terminal windows using these dedicated helper scripts:

- **Terminal 1 (API Server)**:
  `..\.venv\Scripts\python.exe start_api_server.py`
- **Terminal 2 (Telegram Bot)**:
  `..\.venv\Scripts\python.exe start_telegram_bot.py`

---

## 📊 Google Sheets Two-Way Sync Guide

This system uses a **Direct-Push Webhook Architecture** to ensure that your local database and staff spreadsheet are always identical.

### A. Local to Sheet (Push)
1. In your `.env`, set your `GOOGLE_SHEETS_WEBHOOK_URL` provided by your Apps Script.
2. Every time a guest books a room or orders food via Telegram, the system instantly pushes the data to the Cloud.

### B. Sheet to Local (Pull)
To allow staff to edit the Google Sheet and have it update the Telegram bot in real-time:
1. **Ngrok Tunnel**: Run `ngrok http 8000`.
2. **Apps Script**: Copy your Ngrok URL and paste it into the `webhookUrl` variable in your Google Apps Script editor.
3. **Trigger**: Set an `On Edit` trigger in the Apps Script dashboard.
4. **Result**: Changing a "Status" in Google Sheets (e.g., from `BOOKED` to `CHECK_IN`) will instantly send a Telegram message to the guest!

---

## 🛡️ Security & Privacy Compliance

- **Isolation**: Telegram IDs are hash-linked to bookings. No room number entry is required, preventing unauthorized users from "guessing" other guests' rooms.
- **Validation**:
    - **Food Ordering**: The system queries the `status` column. If the guest is not `CHECK_IN`, the order is blocked.
    - **Inventory**: Atomic database transactions prevent double-booking the same physical room.
- **Data Privacy**: All AI processing is performed **locally** via Ollama. No guest data, chat history, or booking info ever leaves your hardware.

---

## 🧹 Database Maintenance
To wipe all test data and reset the 40 physical rooms to "Available":
1. Delete `data/hotel_data.db`.
2. Run `python -m backend.database.setup_db`.
