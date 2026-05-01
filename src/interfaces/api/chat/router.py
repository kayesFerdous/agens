# interfaces/api/chat/router.py — thin adapter: validate → agent.chat() → SSE stream
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db import repository as session_repo
from interfaces.api.chat.schemas import ChatRequest
from config.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and receive the response as an SSE stream.

    SSE event types (each line is `data: {json}\\n\\n`):
        token       — a chunk of the final text answer
        tool_start  — a tool is about to be executed
        tool_end    — a tool finished (with result or error)
        status      — a non-error status update for the UI
        error       — something went wrong
        done        — stream complete with session_id, usage, tool_history
    """
    agent = request.app.state.agent
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="No active API key configured. Add one via POST /api-keys.",
        )

    # Auto-create a session if none provided (first message from this client).
    if body.session_id:
        session = await session_repo.get_session(db, body.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = body.session_id
    else:
        session = await session_repo.insert_session(db, body.message[:60])
        session_id = session.id

    async def event_stream():
        try:
            async for event in agent.chat(body.message, session_id, model=body.model):
                payload: dict = {}

                if event.type == "token":
                    payload = {"type": "token", "content": event.content}

                elif event.type == "tool_start":
                    payload = {
                        "type": "tool_start",
                        "tool": event.tool,
                        "arguments": event.arguments,
                    }

                elif event.type == "tool_end":
                    payload = {
                        "type": "tool_end",
                        "tool": event.tool,
                        "result": event.result,
                        "error": event.error,
                    }

                elif event.type == "status":
                    payload = {"type": "status", "message": event.message}

                elif event.type == "error":
                    payload = {"type": "error", "error": event.error}

                elif event.type == "done":
                    usage_data = None
                    if event.usage:
                        usage_data = {
                            "prompt_tokens": event.usage.prompt_tokens,
                            "completion_tokens": event.usage.completion_tokens,
                            "total_tokens": event.usage.total_tokens,
                        }
                    payload = {
                        "type": "done",
                        "session_id": session_id,
                        "usage": usage_data,
                        "tool_history": [
                            {
                                "tool": tc.tool,
                                "arguments": tc.arguments,
                                "result": tc.result,
                                "error": tc.error,
                            }
                            for tc in event.tool_calls
                        ],
                    }

                yield f"data: {json.dumps(payload)}\n\n"

        except Exception as e:
            logger.exception("Unhandled error in event_stream: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
