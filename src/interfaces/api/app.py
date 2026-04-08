from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent.factory import build_agent
from config.settings import settings
from interfaces.api.sessions.router import router as sessions_router
from interfaces.api.chat.router import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the agent once on startup and store it in app state."""
    app.state.agent = build_agent()
    yield


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

app.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
