from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Text, func
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
