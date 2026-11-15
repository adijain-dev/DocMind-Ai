import io
import json
import asyncio
import threading
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Dict

try:
    from services.qna_engine import generate_answer, stream_answer
    from services.vector_store import get_all_api_names
except ImportError:
    from ..services.qna_engine import generate_answer, stream_answer
    from ..services.vector_store import get_all_api_names

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None


class AskQuestionRequest(BaseModel):
    question: str
    api_name: str
    conversation_history: Optional[List[Dict]] = []


class CompareRequest(BaseModel):
    question: str
    api1: str
    api2: str
    conversation_history: Optional[List[Dict]] = []


class ExportPDFRequest(BaseModel):
    api_name: str
    messages: List[ChatMessage]


@router.post("/chat")
async def ask_question(request: AskQuestionRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if not request.api_name.strip():
        raise HTTPException(status_code=400, detail="Please select an API")
    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: generate_answer(request.question, request.api_name, request.conversation_history or [])
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")


@router.post("/chat/stream")
async def ask_question_stream(request: AskQuestionRequest):
    """Real Groq streaming via thread + asyncio.Queue bridge."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if not request.api_name.strip():
        raise HTTPException(status_code=400, detail="Please select an API")

    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()
    DONE = object()

    def producer():
        try:
            for chunk in stream_answer(request.question, request.api_name, request.conversation_history or []):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, Exception(str(exc)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, DONE)

    t = threading.Thread(target=producer, daemon=True)
    t.start()

    async def event_stream():
        while True:
            item = await queue.get()
            if item is DONE:
                break
            if isinstance(item, Exception):
                yield f"data: {json.dumps({'error': str(item), 'done': True})}\n\n"
                return
            yield f"data: {json.dumps({'text': item, 'done': False})}\n\n"

        yield f"data: {json.dumps({'text': '', 'done': True})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/compare")
async def compare_apis(request: CompareRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    if not request.api1.strip() or not request.api2.strip():
        raise HTTPException(status_code=400, detail="Please select both APIs")
    if request.api1 == request.api2:
        raise HTTPException(status_code=400, detail="Please select two different APIs")
    try:
        loop = asyncio.get_running_loop()
        r1, r2 = await asyncio.gather(
            loop.run_in_executor(None, lambda: generate_answer(request.question, request.api1, request.conversation_history or [])),
            loop.run_in_executor(None, lambda: generate_answer(request.question, request.api2, request.conversation_history or [])),
        )
        return {
            "question": request.question,
            "api1": request.api1,
            "api2": request.api2,
            "answer1": r1.get("answer", ""),
            "answer2": r2.get("answer", ""),
            "tokens1": r1.get("tokens_used", 0),
            "tokens2": r2.get("tokens_used", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compare failed: {str(e)}")


@router.get("/apis")
async def list_available_apis():
    try:
        return {"apis": get_all_api_names()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-pdf")
async def export_chat_pdf(request: ExportPDFRequest):
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(status_code=500, detail="fpdf2 is not installed. Run `pip install fpdf2`.")

    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages to export")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_fill_color(20, 20, 50)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 13, f"  {request.api_name} - Chat Export", fill=True, ln=True)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"  {datetime.now().strftime('%d %b %Y, %I:%M %p')}  |  {len(request.messages)} messages", ln=True)
    pdf.ln(3)

    for msg in request.messages:
        is_user = msg.role == "user"
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(60, 100, 200 if is_user else 30)
        pdf.cell(0, 7, "  You" if is_user else "  Assistant", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(30, 30, 30)

        # Sanitize text for Latin-1 encoding in standard PDF fonts
        content = msg.content
        replacements = {
            "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
            "\u2013": "-", "\u2014": "--", "\u2026": "...", "\u2022": "*"
        }
        for k, v in replacements.items():
            content = content.replace(k, v)
        safe = content.encode("latin-1", errors="replace").decode("latin-1")

        pdf.multi_cell(0, 6, safe)
        if msg.timestamp:
            pdf.set_font("Helvetica", "I", 7)
            pdf.set_text_color(160, 160, 160)
            pdf.cell(0, 5, f"  {msg.timestamp}", ln=True)
        pdf.set_draw_color(220, 220, 220)
        pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
        pdf.ln(4)

    pdf.set_y(-12)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(160, 160, 160)
    pdf.cell(0, 8, f"DocMind AI  |  Page {pdf.page_no()}", align="C")

    filename = f"{request.api_name.replace(' ', '_')}_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        io.BytesIO(bytes(pdf.output())),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
