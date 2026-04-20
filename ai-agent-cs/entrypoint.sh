#!/bin/sh

# ==========================================================
# Hotel AI Agent Unified Startup Script
# ==========================================================

# 1. Wait for Redis (if host is not localhost)
if [ "$REDIS_HOST" != "localhost" ]; then
    echo "Waiting for Redis at $REDIS_HOST:$REDIS_PORT..."
    while ! nc -z $REDIS_HOST $REDIS_PORT; do
      sleep 1
    done
    echo "Redis is up and running!"
fi

# 2. Ensure the data directory exists and has a database
if [ ! -f "data/hotel_data.db" ]; then
    echo "Initializing fresh database..."
    python -m backend.database.setup_db
fi

# 3. Ingest Knowledge Base
echo "Ingesting Knowledge Base..."
python -m backend.data_scripts.ingest_kb

echo "Starting Multi-Process Hotel System..."

# 4. Start API Server (Background)
echo "Launching API Server on port 8000..."
uvicorn backend.api_server:app --host 0.0.0.0 --port 8000 &

# 5. Start Telegram Bot (Foreground)
echo "Launching Telegram Bot..."
python start_telegram_bot.py
