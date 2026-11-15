import os
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Ensure the api directory is in sys.path regardless of execution directory
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from routes import upload, chat, test_api, generate
    from config import UPLOAD_FOLDER, CHROMA_DB_PATH, FRONTEND_DIR
except ImportError:
    from .routes import upload, chat, test_api, generate
    from .config import UPLOAD_FOLDER, CHROMA_DB_PATH, FRONTEND_DIR

app = FastAPI(
    title="DocMind AI — API Documentation Agent",
    description="Interactive Q&A, SDK generation, and documentation tester powered by Groq and ChromaDB"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure data folders exist using absolute paths
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHROMA_DB_PATH, exist_ok=True)

# API Routers
app.include_router(upload.router,   prefix="/api")
app.include_router(chat.router,     prefix="/api")
app.include_router(test_api.router, prefix="/api")
app.include_router(generate.router, prefix="/api")


# Health check route
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Server is running 🚀"}


# Mount frontend static files
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    @app.get("/")
    def home():
        return {"message": "Server is running 🚀 (frontend folder not found)"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
