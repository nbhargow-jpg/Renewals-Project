"""
ai.py — FastAPI router for AI Data Assistant with SSE streaming, tool safety, and rate limiting.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.services.context import UserContext, get_user_context
from backend.services.ai_service import AIService
from backend.services.assistant_tools import AssistantTools
from backend.services.demo_router import DemoRouter
from backend.services.llm_adapter import LLMAdapter

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])

# ---------------------------------------------------------------------------
# Rate Limiting (in-memory per session / IP, 30 requests per minute)
# ---------------------------------------------------------------------------
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 40
_request_timestamps: Dict[str, List[float]] = defaultdict(list)


def check_rate_limit(session_id: str):
    now = time.time()
    ts_list = _request_timestamps[session_id]
    # Prune timestamps older than window
    ts_list[:] = [t for t in ts_list if now - t < RATE_LIMIT_WINDOW]
    if len(ts_list) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a moment before sending another message.",
        )
    ts_list.append(now)


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: Optional[str] = "default_session"
    conversation: Optional[List[Dict[str, Any]]] = []
    scope: Optional[str] = "renewals"
    include_deleted_lost: Optional[bool] = False


class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = "default_session"
    scope: Optional[str] = "renewals"
    include_deleted_lost: Optional[bool] = False


# ---------------------------------------------------------------------------
# Helper execution
# ---------------------------------------------------------------------------
def _execute_assistant(
    db: Session,
    question: str,
    conversation: Optional[List[Dict[str, Any]]] = None,
    user_context: Optional[UserContext] = None,
    scope: str = "renewals",
    include_deleted_lost: bool = False,
) -> Dict[str, Any]:
    """Execute either rule-based DemoRouter or LLMAdapter based on settings."""
    tools = AssistantTools(
        db,
        user_context,
        scope=scope,
        include_deleted_lost=include_deleted_lost,
    )

    is_demo = settings.DEMO_MODE or not settings.LLM_API_KEY
    if is_demo:
        router_svc = DemoRouter(tools)
        res = router_svc.route_and_execute(question)
        return {
            **res,
            "is_demo_mode": True,
            "provider": "demo",
            "model": "rule-based router",
        }

    # External LLM mode
    adapter = LLMAdapter(tools)
    messages = conversation or []
    messages = list(messages) + [{"role": "user", "content": question}]
    answer_text, executed_tools = adapter.run_completion(messages)

    # Collect source links and charts from executed tools
    sources = []
    chart_data = None
    for item in executed_tools:
        tres = item.get("result", {})
        if "link" in tres:
            sources.append({"label": item["tool"].replace("_", " ").title(), "link": tres["link"]})
        if "chart_data" in tres and not chart_data:
            chart_data = tres["chart_data"]

    return {
        "answer": answer_text,
        "tools_called": executed_tools,
        "sources": sources,
        "chart_data": chart_data,
        "is_refusal": False,
        "is_demo_mode": False,
        "provider": "openai_compatible",
        "model": settings.LLM_MODEL,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/config")
def get_ai_config():
    """Return whether the assistant is running in Demo Mode and current config."""
    is_demo = settings.DEMO_MODE or not bool(settings.LLM_API_KEY)
    return {
        "is_demo_mode": is_demo,
        "provider": "demo" if is_demo else "external",
        "model": "demo-rules" if is_demo else settings.LLM_MODEL,
        "send_mode": settings.LLM_SEND_MODE,
        "max_tool_calls": settings.LLM_MAX_TOOL_CALLS,
    }


@router.post("/ask")
async def ask_json(
    body: AskRequest,
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context),
):
    """Standard non-streaming JSON endpoint."""
    check_rate_limit(body.session_id or "default")
    try:
        res = await asyncio.wait_for(
            asyncio.to_thread(
                _execute_assistant,
                db,
                body.question,
                [],
                ctx,
                body.scope or "renewals",
                bool(body.include_deleted_lost),
            ),
            timeout=float(settings.LLM_TIMEOUT),
        )
        return res
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Assistant request timed out.")


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context),
):
    """SSE streaming endpoint for assistant chat."""
    check_rate_limit(body.session_id or "default")

    async def event_generator():
        yield f"event: status\ndata: {json.dumps({'message': 'Analyzing query...'})}\n\n"
        await asyncio.sleep(0.02)

        try:
            res = await asyncio.wait_for(
                asyncio.to_thread(
                    _execute_assistant,
                    db,
                    body.question,
                    body.conversation,
                    ctx,
                    body.scope or "renewals",
                    bool(body.include_deleted_lost),
                ),
                timeout=float(settings.LLM_TIMEOUT),
            )
        except asyncio.TimeoutError:
            yield f"event: error\ndata: {json.dumps({'error': 'Request timed out.'})}\n\n"
            return
        except Exception as exc:
            log.error("Chat error: %s", exc, exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
            return

        # Emit tool calls
        for tc in res.get("tools_called", []):
            yield f"event: tool_call\ndata: {json.dumps(tc)}\n\n"
            await asyncio.sleep(0.02)

        # Stream answer in chunks
        full_text = res.get("answer", "")
        chunk_size = 20
        for i in range(0, len(full_text), chunk_size):
            chunk = full_text[i:i + chunk_size]
            yield f"event: text_chunk\ndata: {json.dumps({'text': chunk})}\n\n"
            await asyncio.sleep(0.01)

        # Emit metadata (sources, chart, tools called for 'Show how I got this')
        meta = {
            "sources": res.get("sources", []),
            "chart_data": res.get("chart_data"),
            "tools_called": res.get("tools_called", []),
            "is_refusal": res.get("is_refusal", False),
            "is_demo_mode": res.get("is_demo_mode", True),
        }
        yield f"event: meta\ndata: {json.dumps(meta)}\n\n"
        yield f"event: done\ndata: {{}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/daily-brief")
def daily_brief(
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context),
):
    svc = AIService(db)
    return svc.daily_brief(ctx)


@router.get("/predictive-insights")
def predictive_insights(
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context),
):
    svc = AIService(db)
    return svc.predictive_insights(ctx)
