from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from enum import Enum as PyEnum
from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: uuid4().hex)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(primary_key=True, default=lambda: uuid4().hex)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(Enum("user", "assistant", name="message_role"))
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["Session"] = relationship(back_populates="messages")



#-------- api key implementation ---------

class KeyStatus(PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"         # Manually disabled
    RATE_LIMITED = "rate_limited" # Temporary cooldown
    EXHAUSTED = "exhausted"       # Daily/quota limit hit
    INVALID = "invalid"           # Revoked or expired at provider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class APIKey(Base):
    __tablename__ = "api_keys"

    # 1. Identification
    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid4().hex
    )
    label: Mapped[str | None] = mapped_column(Text, index=True)   # e.g., "Prod-Gemini-Main"
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)

#------------------------------------------------------------------------
    model_cooldowns: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=dict
    )
    # Stored as:
    # {
    #   "gemini-1.5-pro":  {"until": "2026-04-23T10:30:00Z", "reason": "rate_limit"},
    #   "gemini-2.0-flash": {"until": "2026-04-23T11:00:00Z", "reason": "exhausted"}
    # }
#------------------------------------------------------------------------

    # 2. Security
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    key_hint: Mapped[str] = mapped_column(String(20), nullable=False)

    # 3. Status & Lifecycle
    status: Mapped[KeyStatus] = mapped_column(
        Enum(KeyStatus), nullable=False, default=KeyStatus.ACTIVE, index=True
    )

    # 4. Usage Metrics
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 5. Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=_utcnow
    )

    def __repr__(self) -> str:
        # Intentionally never exposes encrypted_key
        return f"<APIKey id={self.id!r} provider={self.provider!r} hint={self.key_hint!r} status={self.status.value!r}>"
