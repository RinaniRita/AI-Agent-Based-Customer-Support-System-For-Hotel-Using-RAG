# AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG

## Introduction

**AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG** is an extensible proof-of-concept that combines autonomous AI agents with Retrieval-Augmented Generation (RAG) to deliver fast, accurate, and context-aware customer support for hotels. Integrating directly into Telegram, it enables users to seamlessly chat with the hotel's AI assistant. By grounding generative responses in hotel-specific documents (policies, FAQs, reservation records, and local knowledge), the system reduces hallucinations and ensures consistent, trustworthy interactions across booking, guest inquiries, and service requests.

## Features

- **Telegram Bot Integration**: Conversational interface directly accessible on Telegram
- **Local AI Processing**: Runs entirely on local hardware using Ollama for privacy and cost-efficiency
- **Retrieval-Augmented Generation (RAG)**: Enhances responses with relevant hotel-specific knowledge
- **Autonomous AI Agents**: Intelligent agents with confidence scoring and automatic escalation
- **Extensible Architecture**: Modular design for adding new agents and knowledge sources
- **Hotel Knowledge Base**: Pre-loaded with comprehensive hotel policies, services, and local information

## How It Works

### Architecture Overview

```text
User on Telegram → Telegram Bot API → AI Agent → RAG Service → LLM (Ollama) → Response
                                        ↓
                                  Vector Store (FAISS)
                                        ↓
                                Hotel Knowledge Base
```

1. **User Interaction**: Customers send queries via Telegram (e.g., "What time is check-in?")
2. **Agent Processing**: Specialized agents (e.g., Customer Support Agent) handle the query
3. **RAG Retrieval**: Relevant documents are retrieved from the vectorized knowledge base
4. **LLM Generation**: Ollama generates context-aware responses using retrieved information
5. **Response Delivery**: System sends the answer back to the user on Telegram

### Key Components

#### AI Agents

- **Base Agent**: Abstract class with RAG integration and confidence calculation
- **Customer Support Agent**: Handles general inquiries, bookings, and service questions

#### RAG System

- **Vector Store**: FAISS-based storage of document embeddings
- **Embedding Model**: Sentence Transformers for text vectorization
- **Retrieval**: Semantic search with similarity scoring

#### Local LLM

- **Ollama Integration**: Runs open-source models locally (e.g., Qwen2.5 7B)
- **Privacy-First**: No data sent to external APIs

## Setup & Startup Guide

### Prerequisites

- Python 3.8+
- Ollama installed and running
- A Telegram Bot Token (from BotFather on Telegram)
- Git

### Quick Start Guide

Follow these steps to get the project running locally:

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

4. **Configure Environment Variables**
   - Copy `.env.example` to `.env` if not already done.
   - Open `.env` and configure your Telegram bot token:
     ```env
     TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
     ```

5. **Set Up Ollama**
   In a separate terminal, ensure Ollama is running and has the right models:
   ```bash
   ollama serve
   ollama pull qwen2.5:7b-instruct  # Main model
   ollama pull all-MiniLM-L6-v2     # Embedding model
   ```

6. **Process Knowledge Base** (First time only)
   ```bash
   python backend/data_scripts/ingest_kb.py
   ```

7. **Start the Telegram Bot**
   ```bash
   python -m backend.app.main
   ```

### Using the Bot

1. Open Telegram and search for your bot.
2. Click **Start** or type `/start`.
3. Ask the bot hotel-related questions (e.g., "What amenities do you offer?", "What is the check-in time?").

## Project Structure

```text
ai-agent-cs/
├── backend/
│   ├── app/
│   │   ├── agent/              # AI agents
│   │   │   ├── agent.py        # Base agent class
│   │   │   └── customer_support_agent.py
│   │   ├── config.py           # Configuration settings
│   │   ├── main.py             # Telegram application entrypoint
│   │   ├── models/             # Data models
│   │   ├── services/           # Core services
│   │   │   ├── llm_client.py   # Ollama integration
│   │   │   └── rag_service.py  # RAG functionality
│   │   └── utils/              # Utility functions
│   └── data_scripts/           # Data processing scripts
│       ├── ingest_kb.py        # Knowledge base ingestion
│       ├── chunk_kb.py         # Document chunking
│       └── build_vector_store.py
├── data/
│   ├── knowledge_base/         # Hotel documents
│   └── vector_store/           # FAISS index and metadata
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
└── README.md
```

## Configuration

### Environment Variables (.env)

```bash
# Telegram App Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Ollama Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
OLLAMA_EMBEDDING_MODEL=all-MiniLM-L6-v2

# RAG Settings
TOP_K=4
SIMILARITY_THRESHOLD=0.30
MAX_OUTPUT_TOKENS=512
CHUNK_SIZE=500
CHUNK_OVERLAP=80
```

## Future Enhancements

- **Multi-Agent System**: Specialized agents for bookings, complaints
- **Integration APIs**: Connect with actual Property Management Systems
- **Advanced RAG**: Hybrid search, re-ranking
- **Analytics**: Conversation logging and insights
- **Multilingual Support**: Handle multiple languages

## License

This project is licensed under the MIT License - see the LICENSE file for details.
