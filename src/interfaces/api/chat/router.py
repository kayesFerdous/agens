import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

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

    SSE events:
        data: {"token": "..."}        — a chunk of the answer text
        data: {"done": true, ...}     — final event with metadata
        data: {"error": "..."}        — if something goes wrong
    """
    # Auto-create a session if none provided (first message)
    if body.session_id:
        session = await session_repo.get_session(db, body.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        session_id = body.session_id
    else:
        session = await session_repo.insert_session(db)
        session_id = session.id

    agent = request.app.state.agent

    async def event_stream():
        try:
            # Run the synchronous agent.run() in a thread so we don't
            # block the event loop while the ReAct loop executes.
            response = await asyncio.to_thread(
                asyncio.run,
                agent.run(body.message, session_id, db),
            )

            if not response.success:
                yield f"data: {json.dumps({'error': response.error})}\n\n"
                return

            # Stream the answer in chunks (word-by-word)
            answer = response.answer or ""
            words = answer.split(" ")
            for i, word in enumerate(words):
                # Re-add space between words (except before the first word)
                token = f" {word}" if i > 0 else word
                yield f"data: {json.dumps({'token': token})}\n\n"
                await asyncio.sleep(0.02)  # Small delay for streaming feel

            # Final event with metadata
            usage_data = None
            if response.usage:
                usage_data = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            tool_history = [
                {
                    "tool": tc.tool,
                    "arguments": tc.arguments,
                    "result": tc.result,
                    "error": tc.error,
                }
                for tc in (response.tool_history or [])
            ]

            yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'usage': usage_data, 'tool_history': tool_history})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
