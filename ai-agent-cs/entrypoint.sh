#!/bin/bash

# ==========================================================
# Hotel AI Agent Unified Startup Script
# ==========================================================

# 1. Ensure the data directory exists and has a database
# This handles the "first run" in the cloud
if [ ! -f "data/hotel_data.db" ]; then
    echo "Initializing fresh database..."
    python -m backend.database.setup_db
fi

# 2. Ingest Knowledge Base if vector store is missing
if [ ! -d "data/vector_store" ]; then
    echo "Ingesting Knowledge Base..."
    python -m backend.data_scripts.ingest_kb
fi

echo "Starting Multi-Process Hotel System..."

# 3. Start API Server (Background)
# We run it on 0.0.0.0 so it's accessible within the container/cloud
echo "Launching API Server on port 8000..."
uvicorn backend.api_server:app --host 0.0.0.0 --port 8000 &

# 4. Start Telegram Bot (Foreground)
# Keeping this in the foreground so the container stays alive as long as the bot is running
echo "Launching Telegram Bot..."
python start_telegram_bot.py
