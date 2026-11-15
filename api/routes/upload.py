import os
import shutil
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

try:
    from services.document_parser import parse_document
    from services.vector_store import store_document_chunks
    from config import UPLOAD_FOLDER
except ImportError:
    from ..services.document_parser import parse_document
    from ..services.vector_store import store_document_chunks
    from ..config import UPLOAD_FOLDER

router = APIRouter()

# Allowed file types
ALLOWED_EXTENSIONS = [".pdf", ".md", ".markdown", ".txt", ".yaml", ".yml", ".json"]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    api_name: str = Form(...)
):
    """
    Upload → Parse → Store in Vector DB
    """

    # Validate file type
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_extension}' not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validate API name
    api_name = api_name.strip()
    if not api_name:
        raise HTTPException(status_code=400, detail="API name cannot be empty")

    # Ensure upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Save file
    saved_file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    try:
        with open(saved_file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

    # Parse document
    try:
        text_chunks = parse_document(saved_file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")

    if not text_chunks:
        raise HTTPException(status_code=400, detail="Empty or unreadable document")

    # Store in vector DB
    try:
        number_of_chunks = store_document_chunks(
            text_chunks,
            api_name,
            file.filename
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vector DB error: {str(e)}")

    return {
        "success": True,
        "message": "Document processed successfully 🚀",
        "file_name": file.filename,
        "api_name": api_name,
        "chunks_stored": number_of_chunks
    }
