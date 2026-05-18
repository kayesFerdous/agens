# interfaces/web/app.py — FastAPI app factory and async start function
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen
import webbrowser

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agent.agent import Agent
from config.logging import get_logger, setup_logging
from config.settings import settings
from db.database import async_session
from db.repositories.api_key import APIKeyRepository
from interfaces.api_key_state import NO_API_KEYS_SETUP_MESSAGE, has_any_api_keys

setup_logging()
logger = get_logger(__name__)
FRONTEND_DIST = Path(__file__).parent / "dist"


def _public_web_url() -> str:
    host = settings.WEB_HOST
    if host in {"0.0.0.0", "localhost"}:
        host = "127.0.0.1"
    return f"http://{host}:{settings.WEB_PORT}"


def _is_reachable(url: str) -> bool:
    req = UrlRequest(url, method="GET")
    try:
        with urlopen(req, timeout=0.5):
            return True
    except (HTTPError, URLError, OSError):
        return False


async def _open_browser_when_ready() -> None:
    base_url = _public_web_url()
    health_url = f"{base_url}/health"
    deadline = asyncio.get_running_loop().time() + 15.0

    while asyncio.get_running_loop().time() < deadline:
        reachable = await asyncio.to_thread(_is_reachable, health_url)
        if reachable:
            try:
                opened = await asyncio.to_thread(
                    webbrowser.open,
                    base_url,
                    new=0,
                    autoraise=True,
                )
                if opened:
                    logger.info("Opened web browser at %s", base_url)
                else:
                    logger.debug("No browser controller was available for %s", base_url)
            except Exception as exc:  # noqa: BLE001 - browser launch should not affect startup.
                logger.debug("Unable to open browser for web interface: %s", exc)
            return
        await asyncio.sleep(0.2)

    logger.debug("Timed out waiting to open browser for web interface at %s", base_url)


def _create_app(agent: Agent) -> FastAPI:
    """Build the FastAPI application with the shared agent already attached."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Agent is already built — just attach it so routers can reach it.
        app.state.agent = agent
        app.state.active_chat_tasks = {}
        app.state.no_api_keys_at_startup = bool(getattr(agent, "no_api_keys_at_startup", False))
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
        allow_origins=([settings.FRONTEND_LINK] if settings.FRONTEND_LINK else []),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import routers here — not at module level — so this file can be imported
    # without triggering FastAPI route registration for other interfaces.
    from interfaces.api.sessions.router import router as sessions_router
    from interfaces.api.chat.router import router as chat_router
    from interfaces.api.api_keys.router import router as api_keys_router
    from interfaces.api.models.router import router as models_router
    from interfaces.api.prefs.router import router as prefs_router
    from interfaces.api.settings.router import router as settings_router

    app.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
    app.include_router(chat_router, prefix="/chat", tags=["chat"])
    app.include_router(api_keys_router, prefix="/api-keys", tags=["api-keys"])
    app.include_router(models_router, prefix="/api", tags=["models"])
    app.include_router(prefs_router, prefix="/prefs", tags=["prefs"])
    app.include_router(settings_router, prefix="/settings", tags=["settings"])

    app.mount("/static", StaticFiles(directory=FRONTEND_DIST), name="frontend")

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok"}

    @app.post("/shutdown", include_in_schema=False)
    async def shutdown(request: Request):
        """Request a graceful shutdown of the running assistant process."""
        if request.headers.get("x-agens-action") != "shutdown":
            raise HTTPException(status_code=403, detail="Invalid lifecycle request.")

        for task in list(getattr(request.app.state, "active_chat_tasks", {}).values()):
            if not task.done():
                task.cancel()

        request_process_shutdown = getattr(agent, "request_shutdown", None)
        if callable(request_process_shutdown):
            request_process_shutdown("web")

        request_web_shutdown = getattr(request.app.state, "request_web_shutdown", None)
        if callable(request_web_shutdown):
            request_web_shutdown()

        return {"shutdown": True}

    @app.get("/setup/status", include_in_schema=False)
    async def setup_status():
        async with async_session() as db:
            no_api_keys = not await has_any_api_keys(APIKeyRepository(db))
        return {
            "no_api_keys": no_api_keys,
            "message": NO_API_KEYS_SETUP_MESSAGE,
            "command": "agens apikey add <label> <provider> <key>",
        }

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_frontend(path: str):
        api_prefixes = ("sessions", "chat", "api-keys", "api", "prefs", "settings", "setup", "shutdown")
        if path in api_prefixes or path.startswith(tuple(f"{prefix}/" for prefix in api_prefixes)):
            raise HTTPException(status_code=404)
        return FileResponse(FRONTEND_DIST / "index.html")

    return app


async def start_web(agent: Agent, *, open_browser: bool = False) -> None:
    """Start the uvicorn server asynchronously (compatible with asyncio.gather)."""
    app = _create_app(agent)

    config = uvicorn.Config(
        app=app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        log_level='warning' if settings.PRODUCTION else 'info',
        access_log=not settings.PRODUCTION,
    )
    server = uvicorn.Server(config)

    def request_web_shutdown() -> None:
        server.should_exit = True

    app.state.request_web_shutdown = request_web_shutdown
    logger.info("Starting web interface on %s:%d", settings.WEB_HOST, settings.WEB_PORT)
    browser_task: asyncio.Task[None] | None = None
    if open_browser:
        browser_task = asyncio.create_task(
            _open_browser_when_ready(),
            name="web-browser-opener",
        )

    try:
        await server.serve()
    finally:
        if browser_task:
            if not browser_task.done():
                browser_task.cancel()
            await asyncio.gather(browser_task, return_exceptions=True)
