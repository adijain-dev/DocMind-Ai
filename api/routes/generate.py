import json
import io
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq

try:
    from config import GROQ_API_KEY
    from services.vector_store import find_relevant_chunks
except ImportError:
    from ..config import GROQ_API_KEY
    from ..services.vector_store import find_relevant_chunks

router = APIRouter()

MODEL = "llama-3.3-70b-versatile"


def get_groq_client():
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured in .env file.")
    return Groq(api_key=GROQ_API_KEY)


# -------------------- REQUEST MODELS --------------------

class GenerateRequest(BaseModel):
    api_name: str
    language: Optional[str] = "all"


class ReadmeRequest(BaseModel):
    api_name: str
    readme: Optional[str] = None


class SdkDownloadRequest(BaseModel):
    api_name: str
    language: str
    code: str


# -------------------- GENERATE SDK --------------------

@router.post("/generate-sdk")
async def generate_sdk(request: GenerateRequest):

    if not request.api_name.strip():
        raise HTTPException(status_code=400, detail="API name required")

    chunks = find_relevant_chunks(
        "endpoints authentication parameters request response",
        request.api_name,
        how_many=8
    )

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No documentation found. Please upload docs first."
        )

    context = "\n\n---\n\n".join(chunks)

    # Language-specific prompts
    if request.language == "python":
        lang_instruction = "Generate a complete Python SDK class with methods, error handling, and example. Output ONLY code."
    elif request.language == "javascript":
        lang_instruction = "Generate a complete Node.js SDK with async/await and fetch. Output ONLY code."
    elif request.language == "java":
        lang_instruction = "Generate a complete Java SDK using HttpURLConnection. Output ONLY code."
    elif request.language == "curl":
        lang_instruction = "Generate full cURL commands for endpoints. Output ONLY commands."
    else:
        lang_instruction = "Generate SDKs in Python, JavaScript, and cURL with proper sections."

    prompt = f"""
You are an expert SDK generator.

API DOCUMENTATION:
{context}

TASK:
{lang_instruction}

Rules:
- Use placeholders like YOUR_API_KEY
- Make it runnable
- Keep it clean
"""

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4096,
        )

        code = response.choices[0].message.content

        return {
            "success": True,
            "language": request.language,
            "api_name": request.api_name,
            "code": code,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------- GENERATE README --------------------

@router.post("/generate-readme")
async def generate_readme(request: ReadmeRequest):

    if not request.api_name.strip():
        raise HTTPException(status_code=400, detail="API name required")

    chunks = find_relevant_chunks(
        "overview authentication endpoints parameters response errors",
        request.api_name,
        how_many=8
    )

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No documentation found. Please upload docs first."
        )

    context = "\n\n---\n\n".join(chunks)

    prompt = f"""
Generate a professional README.md.

API NAME: {request.api_name}

DOCUMENTATION:
{context}

Include:
- Overview
- Base URL
- Auth
- Endpoints
- Examples
- Errors

Output ONLY markdown.
"""

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4096,
        )

        readme = response.choices[0].message.content

        return {
            "success": True,
            "api_name": request.api_name,
            "readme": readme,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------- DOWNLOAD SDK --------------------

@router.post("/download-sdk")
async def download_sdk_file(request: SdkDownloadRequest):

    extensions = {
        "python": ".py",
        "javascript": ".js",
        "java": ".java",
        "curl": ".sh",
        "all": ".txt"
    }

    ext = extensions.get(request.language.lower(), ".txt")
    filename = f"{request.api_name.replace(' ', '_')}_sdk{ext}"

    return StreamingResponse(
        io.BytesIO(request.code.encode("utf-8")),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# -------------------- DOWNLOAD README --------------------

@router.post("/download-readme")
async def download_readme_file(request: ReadmeRequest):

    if not request.readme:
        raise HTTPException(status_code=400, detail="No README content provided")

    filename = f"{request.api_name.replace(' ', '_')}_README.md"

    return StreamingResponse(
        io.BytesIO(request.readme.encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
