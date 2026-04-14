import os
from dotenv import load_dotenv

# Load environment variables from .env file (root of ai-agent-cs)
# Note: In production Docker, variables are usually provided through the host/dashboard,
# so we load .env only if it exists.
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
else:
    # Fallback to system env vars only
    load_dotenv()

# --------------------------------------------------
# LLM Providers (Cloud)
# --------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY_FALLBACK = os.getenv("GEMINI_API_KEY_FALLBACK", "AIzaSyDakHyHfj6TEdTun30VuxxrUFIeIDVMZuU")
# Model names: "gemini-1.5-flash" or "gemini-1.5-pro"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")


# --------------------------------------------------
# RAG settings
# --------------------------------------------------
TOP_K = int(os.getenv("TOP_K", 4))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", 0.30))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.75))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", 2048))
# Chunking settings
# --------------------------------------------------
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 80))

# --------------------------------------------------
# Vector store settings
# --------------------------------------------------
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "data/vector_store/")
FAISS_INDEX_FILE = os.getenv("FAISS_INDEX_FILE", "faiss_index.index")
METADATA_FILE = os.getenv("METADATA_FILE", "metadata.json")

# --------------------------------------------------
# Application settings
# --------------------------------------------------
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "True").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# --------------------------------------------------
# Optional / future settings
# --------------------------------------------------
RATE_LIMIT = int(os.getenv("RATE_LIMIT", 60))
ENABLE_ESCALATION_LOG = os.getenv("ENABLE_ESCALATION_LOG", "True").lower() == "true"
TICKET_STORAGE_PATH = os.getenv("TICKET_STORAGE_PATH", "data/tickets/")
