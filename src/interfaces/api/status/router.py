from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from config.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/stream")
async def status_stream():
    async def event_stream():
        try:
            while True:
                payload = json.dumps({"status": "active"})
                yield f"data: {payload}\n\n"
                await asyncio.sleep(8)
        except asyncio.CancelledError:
            logger.info("Status stream cancelled")
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
