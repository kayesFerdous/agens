# interfaces/api/chat/router.py — thin adapter: validate → agent.chat() → SSE stream
from __future__ import annotations

import hmac
import json
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from db.database import async_session
from db import repository as session_repo
from interfaces.api.chat.schemas import ChatRequest
from config.logging import get_logger
from config.settings import settings
from core.types import SUDO_AUTHORIZATION_TTL_SECONDS

logger = get_logger(__name__)
router = APIRouter()


class SudoAuthRequest(BaseModel):
    """Request body for POST /authorize-sudo."""
    session_id: str
    secret: str  # the app-level secret — NOT the OS password


@router.post("/authorize-sudo")
async def authorize_sudo(body: SudoAuthRequest, request: Request):
    """Verify the app-level secret and grant single-use sudo authorization for a session.

    Security properties:
    - Uses hmac.compare_digest (timing-safe — not ==)
    - Never logs the provided secret
    - Never stores the secret anywhere
    - Does NOT write to DB or message history (intentional — no audit trail in LLM context)
    """
    agent = request.app.state.agent
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized.")

    if not settings.AGENT_SUDO_SECRET:
        raise HTTPException(
            status_code=501,
            detail="Sudo authorization is not configured on this server.",
        )

    # Timing-safe comparison — never use == for secrets
    is_valid = hmac.compare_digest(
        body.secret.encode("utf-8"),
        settings.AGENT_SUDO_SECRET.encode("utf-8"),
    )

    if not is_valid:
        # Log session_id only — never log the provided secret
        logger.warning(
            "Sudo authorization failed — invalid secret",
            extra={"session_id": body.session_id},
        )
        raise HTTPException(status_code=403, detail="Invalid secret.")

    agent._sudo_authorized_sessions[body.session_id] = time.time()
    logger.info(
        "Sudo authorization granted",
        extra={"session_id": body.session_id, "expires_in": SUDO_AUTHORIZATION_TTL_SECONDS},
    )

    return {"authorized": True, "expires_in": SUDO_AUTHORIZATION_TTL_SECONDS}


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
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

    # Resolve the session_id in a short-lived DB connection that is fully
    # closed BEFORE the StreamingResponse is returned. This prevents the
    # SQLAlchemy / aiosqlite "Connection closed" crash that occurs when
    # FastAPI's dependency teardown tries to rollback a session that
    # outlived a disconnected streaming response.
    async with async_session() as db:
        if body.session_id:
            session = await session_repo.get_session(db, body.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = body.session_id
        else:
            session = await session_repo.insert_session(db, body.message[:60])
            session_id = session.id
    # `db` is now fully closed — the streaming generator below uses
    # agent.chat(), which opens its own independent session internally.

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

                elif event.type == "confirmation_required":
                    payload = {
                        "type": "confirmation_required",
                        "tool": event.tool,
                        "arguments": event.arguments,
                        "reason": event.confirmation_reason,
                        "preview": event.confirmation_preview,
                    }

                elif event.type == "confirmation_result":
                    payload = {
                        "type": "confirmation_result",
                        "tool": event.tool,
                        "result": event.result,
                        "error": event.error,
                        "message": event.message,
                    }

                elif event.type == "sudo_auth_required":
                    # Tell the frontend to prompt for the app secret via POST /authorize-sudo.
                    # session_id is deliberately omitted — frontend already holds it.
                    payload = {
                        "type": "sudo_auth_required",
                        "preview": event.confirmation_preview,
                    }

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
                        "next_action": event.next_action,
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
