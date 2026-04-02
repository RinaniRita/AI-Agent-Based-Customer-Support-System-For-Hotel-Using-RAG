---
description: How to start and manage the backend bot and API server
---

# Starting the Hotel AI Backend Services

## Pre-flight Check
// turbo-all

Before starting any services, ALWAYS check if they are already running by using `command_status` on any known terminal command IDs.

## 1. Start the Telegram Bot
```powershell
d:\work\DSP\AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG\.venv\Scripts\python.exe -m backend.app.main
```
Working directory: `d:\work\DSP\AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG\ai-agent-cs`

This runs as a long-lived background process. Verify it starts by checking for `Application started` in the output.

## 2. Start the FastAPI Server (for booking confirmations & kitchen push)
```powershell
d:\work\DSP\AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG\.venv\Scripts\python.exe -m uvicorn web_server:app --port 8000
```
Working directory: `d:\work\DSP\AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG\ai-agent-cs`

Verify it starts by checking for `Uvicorn running on http://127.0.0.1:8000`.

## 3. Re-initialize the Database (if needed)
```powershell
d:\work\DSP\AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG\.venv\Scripts\python.exe -m backend.database.setup_db
```

## Important Notes
- If you edit `main.py`, you MUST restart the bot (terminate and re-run step 1).
- The API server with `--reload` will auto-restart on code changes, but without it you must manually restart.
- Always verify syntax BEFORE restarting: `python -c "import py_compile; py_compile.compile(r'path/to/main.py', doraise=True)"`
- The dummy test guest is in Room 101 (Jane Doe, CONFIRMED booking).
