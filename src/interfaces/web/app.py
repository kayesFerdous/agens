# interfaces/web/app.py — FastAPI app factory and async start function
from __future__ import annotations

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.agent import Agent
from config.logging import get_logger, setup_logging
from config.settings import settings

setup_logging()
logger = get_logger(__name__)


def _create_app(agent: Agent) -> FastAPI:
    """Build the FastAPI application with the shared agent already attached."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Agent is already built — just attach it so routers can reach it.
        app.state.agent = agent
        # fernet lives on the agent; expose it here for the api-keys router
        # which needs it to encrypt keys added via the REST API.
        app.state.fernet = agent._fernet
        logger.info("Web interface ready")
        yield
        logger.info("Web interface shutting down")

    app = FastAPI(
        title="Assistant API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_LINK],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import routers here — not at module level — so this file can be imported
    # without triggering FastAPI route registration for other interfaces.
    from interfaces.api.sessions.router import router as sessions_router
    from interfaces.api.chat.router import router as chat_router
    from interfaces.api.api_keys.router import router as api_keys_router
    from interfaces.api.settings.router import router as settings_router

    app.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
    app.include_router(chat_router, prefix="/chat", tags=["chat"])
    app.include_router(api_keys_router, prefix="/api-keys", tags=["api-keys"])
    app.include_router(settings_router, prefix="/settings", tags=["settings"])

    return app


async def start_web(agent: Agent) -> None:
    """Start the uvicorn server asynchronously (compatible with asyncio.gather)."""
    app = _create_app(agent)

    config = uvicorn.Config(
        app=app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logger.info("Starting web interface on %s:%d", settings.WEB_HOST, settings.WEB_PORT)
    await server.serve()
