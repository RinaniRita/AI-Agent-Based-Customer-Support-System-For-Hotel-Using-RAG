from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import uvicorn
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .services.llm_client import LLMClient
from .services.rag_service import RAGService
from .agent.customer_support_agent import CustomerSupportAgent
from .config import (
    HOST,
    PORT,
)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
llm_client = LLMClient()
# RAGService now reads model + paths from config by default
rag_service = RAGService()

# Initialize agent
support_agent = CustomerSupportAgent("CustomerSupport", llm_client, rag_service)


# Paths for serving the frontend
BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"
INDEX_FILE = FRONTEND_DIR / "index.html"

# FastAPI app
app = FastAPI(
    title="AI Hotel Support System",
    description="AI-powered customer support for hotels using RAG",
    version="1.0.0",
)

# enable CORS for frontend testing (kept broad while iterating)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # adjust to specific domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static frontend so one port (8000) handles both UI and API
if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static",
    )


@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the main frontend page."""
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    raise HTTPException(status_code=404, detail="Frontend not found")


@app.get("/style.css", include_in_schema=False)
async def serve_style():
    """Serve the main stylesheet for the frontend."""
    css_path = FRONTEND_DIR / "style.css"
    if css_path.exists():
        return FileResponse(css_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS not found")


@app.get("/script.js", include_in_schema=False)
async def serve_script():
    """Serve the main script for the frontend."""
    js_path = FRONTEND_DIR / "script.js"
    if js_path.exists():
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JS not found")

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str
    confidence: float
    needs_escalation: bool
    agent: str

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Process a customer support chat message.
    """
    try:
        logger.info(f"Processing chat request: {request.message[:50]}...")

        # Process with the support agent
        result = support_agent.process_query(
            user_query=request.message,
            context=request.user_context or {}
        )

        return ChatResponse(
            response=result['response'],
            confidence=result['confidence'],
            needs_escalation=result['needs_escalation'],
            agent=result['agent']
        )

    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": support_agent.name}

@app.get("/capabilities")
async def get_capabilities():
    """Get agent capabilities."""
    return {"capabilities": support_agent.get_capabilities()}

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)