import os
from dotenv import load_dotenv

# Base directory for the API package
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load .env from api/ directory first, then fallback to current directory
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Pinecone settings (optional / legacy)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "api-qna-agent")

# Absolute path configurations to prevent CWD dependency issues
UPLOAD_FOLDER = os.path.join(BASE_DIR, "data", "uploads")
CHROMA_DB_PATH = os.path.join(BASE_DIR, "data", "chroma_db")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

MAX_CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
