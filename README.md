# AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG

## Introduction

**AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG** is an extensible proof-of-concept that combines autonomous AI agents with Retrieval-Augmented Generation (RAG) to deliver fast, accurate, and context-aware customer support for hotels. Using Telegram as the primary guest interface, it seamlessly blends conversational AI with a **full-stack physical room booking system**.

By grounding generative responses in local hotel documents and integrating a real-time reservation state machine, the system reduces hallucinations, prevents illogical bookings (e.g., past dates), tracks physical room inventory, and offers a smooth checkout flow through a static web frontend.

## Features

- **Telegram Bot Integration**: Conversational interface directly accessible on Telegram.
- **Physical Inventory Engine**: Actively manages 40 physical hotel rooms (Rooms 101 to 805) across 8 different price tiers, preventing overbooking.
- **Time-Aware Booking Validation**: AI automatically catches and rejects past-date check-ins using real-time system clock validation.
- **GitHub Pages Frontend Integration**: Seamlessly generates and sends a checkout URL connected to a responsive, glassmorphism-themed static web interface.
- **FastAPI JSON Backend**: A robust REST API running natively with CORS enabled to serve the static frontend.
- **Local AI Processing**: Runs entirely on local hardware using Ollama for privacy and cost-efficiency.
- **Retrieval-Augmented Generation (RAG)**: Enhances responses with relevant hotel-specific knowledge.

## How It Works

### Architecture Overview

```text
       [Telegram Bot] <──────> [Main.py State Machine & RAG Agent]
             │                              │
             ▼                              ▼
    [GitHub Pages Frontend]         [Local Ollama / FAISS]
 (review.html & payment.html)               │
             │                              ▼
             └─────────> [FastAPI JSON Backend] <──────> [SQLite DB (Internal)]
                         (Serves /api/booking)             (40 Physical Rooms)
```

1. **User Interaction**: Customers chat with the AI on Telegram to ask questions or start a booking.
2. **State Machine**: The bot enters a 4-step booking flow handling Dates → Name → Email → Phone.
3. **Inventory Management**: The database finds a specific empty physical room (e.g., Room #402) for those exact dates and assigns it.
4. **Handoff**: The Bot generates a URL pointing to the static GitHub Pages frontend.
5. **Checkout**: The GitHub Pages site uses JavaScript (`fetch`) to call the FastAPI backend, displaying the booking details and completing the payload securely.

## Setup & Startup Guide

### Prerequisites

- Python 3.8+
- Ollama installed and running
- A Telegram Bot Token (from BotFather on Telegram)
- Git

### Quick Start Guide

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd ai-agent-cs
   ```

2. **Create and Activate Virtual Environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize Physical Database**
   ```bash
   python -m backend.database.setup_db
   ```
   *(This ensures all 40 physical rooms are populated correctly).*

5. **Configure Environment Variables**
   - Copy `.env.example` to `.env` if not already done.
   - Configure your keys and GitHub pages URL:
     ```env
     TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
     FRONTEND_URL=https://your-username.github.io/repo-name/github_pages_frontend
     ```

6. **Set Up Ollama (in a separate terminal)**
   ```bash
   ollama serve
   ollama pull qwen2.5:7b-instruct  # Main model
   ollama pull all-MiniLM-L6-v2     # Embedding model
   ```

7. **Start the API Server (Terminal 1)**
   ```bash
   uvicorn web_server:app --reload
   ```

8. **Start the Telegram Bot (Terminal 2)**
   ```bash
   python -m backend.app.main
   ```

9. **Host the Frontend**
   - Upload the `github_pages_frontend` folder to a GitHub repository.
   - Enable GitHub Pages on the `main` branch.
   - Update `FRONTEND_URL` in `.env` or `main.py` with your live link.

## 🔄 Switching Between Local and Live (GitHub Pages)

Because your GitHub Pages site uses secure (`https://`), modern browsers will block it from fetching data from an insecure local computer (`http://localhost:8000`). Depending on how you are testing the system, follow these configurations:

### Option 1: Fully Local Development
If you just want to test on your own computer without deploying or opening tunnels:
1. In `main.py`, set:
   `FRONTEND_URL = "http://127.0.0.1:5500/github_pages_frontend"` (or whatever local port you are using to serve the HTML folder, e.g. via VSCode Live Server).
2. In `review.html` and `payment.html`, set:
   `const API_BASE_URL = 'http://localhost:8000';`

### Option 2: Live GitHub Pages + Local Backend (Using Ngrok)
To test the live GitHub frontend while running the backend securely from your laptop:
1. Start Ngrok targeting your FastAPI backend: `ngrok http 8000`
2. Copy the secure Ngrok URL (e.g., `https://123-abc.ngrok-free.app`).
3. In `review.html` and `payment.html`, update the JavaScript:
   `const API_BASE_URL = 'https://123-abc.ngrok-free.app';`
4. Commit and push those changes to GitHub.
5. In `main.py`, ensure `FRONTEND_URL` is set to your GitHub Pages URL (e.g., `https://your-username.github.io/ai-agent-cs/github_pages_frontend`).

---

## Project Structure

```text
ai-agent-cs/
├── backend/
│   ├── app/
│   │   ├── agent/              # AI Agents and Confidence Scoring
│   │   ├── main.py             # Telegram Application & State Machine
│   │   └── services/           # RAG and LLM coordination
│   ├── database/               
│   │   ├── db_service.py       # SQLite CRUD & Physical Inventory queries
│   │   └── setup_db.py         # 40-Room Seeding Script
│   └── data_scripts/           # Vector DB compilation scripts
├── data/
│   ├── knowledge_base/         # Hotel markdown documents
│   ├── vector_store/           # FAISS index
│   └── hotel_data.db           # SQLite database
├── github_pages_frontend/      # Static Web UI for GitHub Pages
│   ├── review.html
│   └── payment.html
├── web_server.py               # FastAPI JSON Backend (CORS enabled)
├── requirements.txt            
└── README.md
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
