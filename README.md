# 🏨 Luxury Hotel AI Agent Management System (V2)

## ✨ Overview
A professional, production-ready AI Agent framework designed to revolutionize hotel operations. This system integrates **Google Gemini 1.5 Flash**, **RAG (Retrieval-Augmented Generation)**, and a **Real-Time Physical Inventory Engine** into a unified Telegram interface.

Built for the modern hospitality industry, it handles everything from secure bookings and in-room dining to front-desk services with 100% data isolation and real-time Google Sheets synchronization.

---

## 🚀 Key Features

*   **🤖 Advanced AI Concierge**: Powered by **Google Gemini**, providing warm, professional, and highly accurate answers grounded in your hotel's private Knowledge Base.
*   **🔐 Secure Identity Mapping**: Telegram IDs are hard-linked to bookings. Guests never need to remember a room number; the bot knows exactly who they are and where they are staying.
*   **🛡️ Checked-In Policy Enforcement**: Room service and front-desk requests are strictly limited to guests who are currently **"Checked In"** in the system.
*   **🍽️ Interactive In-Room Dining**: A full digital menu with category browsing, wine pairings, and a **Live Order Tracker** (Received → Preparing → Plating → Delivered).
*   **🔄 Bi-Directional Google Sheets Sync**: Instant synchronization between the local SQLite database and a staff-facing Google Sheet. Staff can update statuses in the sheet, and the bot notifies the guest instantly via Telegram.
*   **📦 Dockerized Deployment**: Fully containerized architecture for reliable "one-click" deployment across any cloud provider (Koyeb, Railway, Render, or VPS).

---

## 🏗️ Project Architecture

```text
ai-agent-cs/
├── backend/
│   ├── api_server.py        # FastAPI: Handles external webhooks (Sheets/Web)
│   ├── bot_server.py        # Telegram Bot: Main State Machine & UX
│   ├── agent/               # AI Logic: Intent classifiers & Prompt engineering
│   ├── database/            # Data Layer: Physical room inventory & SQL logic
│   ├── data_scripts/        # KB Ingest: Auto-builds FAISS Vector Stores
│   └── services/            # Business Logic: Room, Food, User, and Sync services
├── data/
│   ├── knowledge_base/      # Your Hotel's Markdown documentation
│   ├── vector_store/        # FAISS Index (Generated automatically)
│   └── hotel_data.db        # Production SQLite Database
├── Dockerfile               # Production Container Definition
└── entrypoint.sh            # Automated Database & RAG Initializer
```

---

## 🛠️ Quick Setup (Docker)

The fastest way to get the system running is using Docker.

### 1. Configure Environment
Create a `.env` file in the root directory:
```bash
GEMINI_API_KEY=your_key_here
TELEGRAM_BOT_TOKEN=your_token_here
GOOGLE_SHEETS_WEBHOOK_URL=your_apps_script_url
BACKEND_WEBHOOK_URL=your_ngrok_or_domain_url
```

### 2. Build & Run
```bash
# Build the production image
docker build -t hotel-ai-agent .

# Run the container (Maps data for persistence)
docker run -d \
  --name hotel-agent \
  -p 8000:8000 \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  hotel-ai-agent
```
*Note: The container automatically initializes the database and ingests the knowledge base on the first run.*

---

## 📊 Staff Management (Google Sheets)

The system is designed to work alongside your existing staff workflows in Google Sheets.

1.  **Staff Editing**: When staff updates a status to `CHECK_IN` or `CHECK_OUT` in the spreadsheet, the bot instantly sends a professional notification to the guest.
2.  **Kitchen Updates**: When the kitchen marks a food order as `DELIVERED` in the sheet, the guest's "Track Order" board updates in real-time.
3.  **Data Capture**: Every booking now captures the **Guest Email**, Phone, and Room Type for your CRM.

---

## 🤖 AI Concierge Intelligence

The bot doesn't just "chat"—it thinks. It uses a multi-stage intent classifier:
1.  **Intent Classifier**: Determines if the user wants to book, order food, or just ask a question.
2.  **Menu Routing**: A simple query like "I'm hungry" or "menu" bypasses general chat and instantly opens the interactive dining cards.
3.  **RAG Grounding**: General questions about WiFi, pet policies, or local area info are strictly answered using your provide Markdown files in `data/knowledge_base/` to prevent AI hallucinations.

---

## 🧽 Maintenance & Cleaning
To reset the system for a new testing phase:
1.  Stop the container: `docker stop hotel-agent`
2.  Delete the database: `rm data/hotel_data.db`
3.  Start the container: The `entrypoint.sh` will auto-generate a fresh 40-room inventory and re-index the Knowledge Base.

---

## 🛡️ Security & Privacy
*   **Privacy**: Powered by Gemini 1.5 Flash via API.
*   **Isolation**: Strict row-level security based on Telegram Chat IDs.
*   **Validation**: Regex-based input validation for names and emails ensures high-quality data.
