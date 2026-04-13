from contextlib import asynccontextmanager

from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.logging import get_logger, setup_logging
from config.settings import settings
from interfaces.api.sessions.router import router as sessions_router
from interfaces.api.chat.router import router as chat_router
from interfaces.api.api_keys.router import router as api_keys_router


setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared app state."""
    app.state.fernet = Fernet(settings.FERNET_SECRET)
    app.state.agent = None
    logger.info("API lifespan initialized")
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
app.include_router(api_keys_router, prefix="/api-keys", tags=["api-keys"])
