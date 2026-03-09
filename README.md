# AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG

## Introduction

**AI-Agent-Based-Customer-Support-System-For-Hotel-Using-RAG** is an extensible proof-of-concept that combines autonomous AI agents with Retrieval-Augmented Generation (RAG) to deliver fast, accurate, and context-aware customer support for hotels. By grounding generative responses in hotel-specific documents (policies, FAQs, reservation records, and local knowledge), the system reduces hallucinations and ensures consistent, trustworthy interactions across booking, guest inquiries, and service requests. Designed for real-world integration, it supports seamless connectivity with property management systems and messaging channels, enabling automated resolution of routine tasks while escalating complex issues to human staff when needed.

## Features

- **Local AI Processing**: Runs entirely on local hardware using Ollama for privacy and cost-efficiency
- **Retrieval-Augmented Generation (RAG)**: Enhances responses with relevant hotel-specific knowledge
- **Autonomous AI Agents**: Intelligent agents with confidence scoring and automatic escalation
- **RESTful API**: FastAPI-based backend for easy integration
- **Extensible Architecture**: Modular design for adding new agents and knowledge sources
- **Hotel Knowledge Base**: Pre-loaded with comprehensive hotel policies, services, and local information

## How It Works

### Architecture Overview

```
User Query → FastAPI Backend → AI Agent → RAG Service → LLM (Ollama) → Response
                                      ↓
                               Vector Store (FAISS)
                                      ↓
                             Hotel Knowledge Base
```

1. **User Interaction**: Customers send queries via API (e.g., "What time is check-in?")
2. **Agent Processing**: Specialized agents (e.g., Customer Support Agent) handle the query
3. **RAG Retrieval**: Relevant documents are retrieved from the vectorized knowledge base
4. **LLM Generation**: Ollama generates context-aware responses using retrieved information
5. **Response & Escalation**: System returns answer with confidence score; escalates if needed

### Key Components

#### AI Agents

- **Base Agent**: Abstract class with RAG integration and confidence calculation
- **Customer Support Agent**: Handles general inquiries, bookings, and service questions
- **Future Agents**: Booking, Complaints, Local Recommendations

#### RAG System

- **Vector Store**: FAISS-based storage of document embeddings
- **Embedding Model**: Sentence Transformers for text vectorization
- **Retrieval**: Semantic search with similarity scoring

#### Local LLM

- **Ollama Integration**: Runs open-source models locally (e.g., Qwen2.5 7B)
- **Privacy-First**: No data sent to external APIs
- **Cost-Effective**: No API usage fees

## Setup & Installation

### Prerequisites

- Python 3.8+
- Ollama installed and running
- Git

### Quick Start (Recommended)

If you have all prerequisites installed:

```bash
# Clone and setup
git clone <repository-url>
cd ai-agent-cs

# Activate virtual environment
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Start Ollama (in separate terminal)
ollama serve

# Pull models
ollama pull qwen2.5:7b-instruct
ollama pull all-MiniLM-L6-v2

# Start the application
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/docs` for API documentation or `http://localhost:3000` for the chat interface.

### Detailed Installation Steps

1. **Clone the Repository**

   ```bash
   git clone <repository-url>
   cd ai-agent-cs
   ```

2. **Create Virtual Environment**

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

4. **Set Up Ollama**

   ```bash
   # Install Ollama from https://ollama.ai
   ollama pull qwen2.5:7b-instruct  # Main model
   ollama pull all-MiniLM-L6-v2     # Embedding model
   ollama serve                     # Start server (keep running)
   ```

5. **Process Knowledge Base** (Already done - skip if vector store exists)

   ```bash
   python backend/data_scripts/ingest_kb.py
   ```

6. **Start the Backend API**

   ```bash
   python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
   ```

7. **Start the Frontend** (Optional - for chat interface)

   ```bash
   # In a new terminal
   cd frontend
   python -m http.server 3000
   ```

## Usage

### Web Interface (Recommended)

1. Start the backend: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
2. Start the frontend: `cd frontend && python -m http.server 3000`
3. Open `http://localhost:3000` in your browser
4. Start chatting with your AI hotel assistant!

### API Endpoints

#### Health Check

```bash
GET /health
```

Response: `{"status": "healthy", "agent": "CustomerSupport"}`

#### Chat Interface

```bash
POST /chat
Content-Type: application/json

{
  "message": "What are the check-in times?",
  "session_id": "optional_session_id",
  "user_context": {}
}
```

Response:

```json
{
  "response": "Check-in time is 3:00 PM...",
  "confidence": 0.85,
  "needs_escalation": false,
  "agent": "CustomerSupport"
}
```

#### Agent Capabilities

```bash
GET /capabilities
```

Response: `{"capabilities": ["general_inquiries", "booking_assistance", ...]}`

### Example Queries

- "What amenities does the hotel offer?"
- "How do I book a room?"
- "What are the cancellation policies?"
- "Are pets allowed?"
- "What's the WiFi password?"

### Testing with curl

```bash
# Health check
curl http://localhost:8000/health

# Chat test
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{"message": "What amenities does the hotel offer?"}'
```

## Project Structure

```
ai-agent-cs/
├── backend/
│   ├── app/
│   │   ├── agent/              # AI agents
│   │   │   ├── agent.py        # Base agent class
│   │   │   └── customer_support_agent.py
│   │   ├── config.py           # Configuration settings
│   │   ├── main.py             # FastAPI application
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
├── frontend/                   # Future UI components
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
└── README.md
```

## Configuration

### Environment Variables (.env)

```bash
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

### Customization

- **Add New Agents**: Extend `BaseAgent` in `agent/` folder
- **Expand Knowledge Base**: Add documents to `data/knowledge_base/`
- **Change Models**: Update `OLLAMA_MODEL` in config
- **Tune RAG**: Adjust `TOP_K`, `SIMILARITY_THRESHOLD` for retrieval

## Development

### Running Tests

```bash
# Test Ollama connection
python test_ollama.py

# Run with reload for development
python -m uvicorn backend.app.main:app --reload
```

### Adding New Features

1. **New Agent**: Create class inheriting from `BaseAgent`
2. **New Endpoint**: Add route in `main.py`
3. **New Knowledge**: Run ingestion scripts after adding documents

## Future Enhancements

- **Multi-Agent System**: Specialized agents for bookings, complaints
- **Frontend Interface**: Web-based chat UI
- **Integration APIs**: Connect with PMS, messaging platforms
- **Advanced RAG**: Hybrid search, re-ranking
- **Analytics**: Conversation logging and insights
- **Multilingual Support**: Handle multiple languages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Ollama for local LLM hosting
- Sentence Transformers for embeddings
- FAISS for vector search
- FastAPI for the web framework
