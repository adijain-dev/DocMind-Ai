import httpx
import json
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter()


class TestAPIRequest(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = {}
    body: Optional[str] = None
    timeout: Optional[int] = 10


class TestAPIResponse(BaseModel):
    status_code: int
    response_time_ms: float
    headers: Dict[str, str]
    body: Any
    success: bool


@router.post("/test", response_model=TestAPIResponse)
async def test_api_endpoint(request: TestAPIRequest):
    """
    🧪 API Tester — Sends real HTTP requests to endpoints and returns latency, headers, and body.
    """
    method = request.method.upper()
    if method not in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
        raise HTTPException(status_code=400, detail=f"Method '{method}' is not supported")

    if not request.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    # Body parsing: support JSON (dict or list) and plain text
    parsed_json = None
    raw_content = None

    if request.body and request.body.strip():
        try:
            parsed_data = json.loads(request.body)
            if isinstance(parsed_data, (dict, list)):
                parsed_json = parsed_data
            else:
                raw_content = request.body.encode("utf-8")
        except json.JSONDecodeError:
            raw_content = request.body.encode("utf-8")

    try:
        start_time = time.monotonic()

        async with httpx.AsyncClient(
            timeout=request.timeout,
            follow_redirects=True
        ) as client:
            response = await client.request(
                method=method,
                url=request.url,
                headers=request.headers or {},
                json=parsed_json,
                content=raw_content,
            )

        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Try parsing response as JSON, fallback to text
        try:
            body = response.json()
        except Exception:
            body = response.text

        return TestAPIResponse(
            status_code=response.status_code,
            response_time_ms=round(elapsed_ms, 2),
            headers=dict(response.headers),
            body=body,
            success=response.is_success
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=408,
            detail=f"Request timed out after {request.timeout}s"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Failed to connect to the target server. Please check the URL."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
