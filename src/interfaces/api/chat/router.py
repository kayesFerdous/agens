import json
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from agent.factory import build_agent
from db.database import get_db
from db import repository as session_repo
from interfaces.api.chat.schemas import ChatRequest

router = APIRouter()


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and receive the response as an SSE stream.

    SSE events (each line is `data: {json}\n\n`):
        type: "tool_start"  — a tool is about to be executed
        type: "tool_end"    — a tool finished (with result or error)
        type: "token"       — a chunk of the final text answer
        type: "status"      — a non-error status update for the UI
        type: "error"       — something went wrong
        type: "done"        — stream complete with session_id, usage, tool_history
    """
    # Auto-create a session if none provided (first message)
    if body.session_id:
        session = await session_repo.get_session(db, body.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = body.session_id
    else:
        session = await session_repo.insert_session(db, body.message[:60])
        session_id = session.id

    agent = request.app.state.agent
    if agent is None:
        try:
            agent = await build_agent(db, request.app.state.fernet)
        except RuntimeError as e:
            # Keep server usable before first key is configured.
            raise HTTPException(
                status_code=503,
                detail="No active API key configured. Add one via POST /api-keys.",
            ) from e
        request.app.state.agent = agent

    async def event_stream():
        try:
            async for event in agent.run_stream(body.message, session_id, db):
                payload = {}

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

                elif event.type == "error":
                    payload = {"type": "error", "error": event.error}

                elif event.type == "status":
                    payload = {
                        "type": "status",
                        "message": event.message,
                    }

                elif event.type == "done":
                    usage_data = None
                    if event.usage:
                        usage_data = {
                            "prompt_tokens": event.usage.prompt_tokens,
                            "completion_tokens": event.usage.completion_tokens,
                            "total_tokens": event.usage.total_tokens,
                        }
                    tool_history = [
                        {
                            "tool": tc.tool,
                            "arguments": tc.arguments,
                            "result": tc.result,
                            "error": tc.error,
                        }
                        for tc in event.tool_calls
                    ]
                    payload = {
                        "type": "done",
                        "session_id": session_id,
                        "usage": usage_data,
                        "tool_history": tool_history,
                    }

                yield f"data: {json.dumps(payload)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
